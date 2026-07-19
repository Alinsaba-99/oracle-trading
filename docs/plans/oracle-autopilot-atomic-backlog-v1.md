# Oracle Autopilot — Master Atomic Roadmap

> **DEPRECATO — archivio storico, non eseguibile.** Questo documento conserva intenti e
> decisioni di una pianificazione precedente. Non rappresenta stato verificato, backlog
> corrente o autorizzazione operativa. Le fonti canoniche sono la Master Roadmap e
> Oracle Autopilot Status nella directory docs.


> Versione: 1.0
> Data baseline: 2026-07-18
> Obiettivo finale: portfolio futures/prop-firm gestito autonomamente da un
> Investment Committee LLM, con intelligence alternativa ElizaOS, risk kernel
> deterministico, OMS e ledger durevoli, paper/shadow trading real-time e
> rollout graduale su capitale reale.

---

## 0. Regole operative della roadmap

### 0.1 Stati ammessi

- `[ ]` non iniziata;
- `[~]` in corso;
- `[x]` completata e verificata;
- `[!]` bloccata con blocker documentato;
- `[-]` rimossa con ADR che ne spiega il motivo.

### 0.2 Regola di atomicità

Una task è completabile in una singola modifica verificabile. Una task non può
contenere contemporaneamente design, implementazione, migrazione e rollout.
Quando emergono più risultati, la task deve essere suddivisa prima di procedere.

### 0.3 Definition of Done universale

Una task è `[x]` soltanto quando:

1. il risultato richiesto esiste nel repository o nell'ambiente previsto;
2. i test mirati sono verdi;
3. Ruff/formatter/mypy o typecheck equivalenti sono verdi;
4. non sono stati introdotti segreti o dati sensibili;
5. documentazione e configurazione sono coerenti;
6. l'evidenza di verifica è registrata nel report della milestone;
7. non rimangono TODO impliciti nella stessa task.

### 0.4 Regola di ripresa

Per riprendere il progetto:

1. leggere `docs/ORACLE_AUTOPILOT_STATUS.md`;
2. verificare il commit e la working tree;
3. eseguire i gate indicati nel file di stato;
4. selezionare la prima task `[ ]` con dipendenze completate;
5. marcarla `[~]` prima della modifica;
6. eseguire test e aggiornare stato/evidenza;
7. marcarla `[x]` solo dopo verifica fresca.

### 0.5 Invarianti non negoziabili

- L'LLM decide portfolio, rebalancing, trade intent ed execution preference.
- L'LLM non scrive direttamente sul broker.
- Ogni ordine attraversa risk kernel e OMS.
- Il ledger riconciliato è la sola fonte autorevole del portfolio.
- Dati, news e memoria rispettano `event_time`, `available_at` e provenance.
- Un dato incerto o stale produce `NO_TRADE`, `PAUSE` o `FLATTEN`.
- Nessun profilo prop-firm sconosciuto può operare live.
- Replay, paper, shadow, evaluation e funded sono ambienti separati.
- Ogni decisione è riproducibile da input, prompt, modello, tool e codice.
- Nessun rendimento futuro o passaggio di challenge è garantito.

---

# Programma A — Fondazioni e controllo del progetto

## M00 — Governance, repository e tracciabilità

**Dipendenze:** nessuna.
**Exit gate:** working tree comprensibile, backlog tracciabile, artefatti generati
separati dal sorgente e stato riprendibile.

- [x] `M00-001` Creare il file di stato operativo della roadmap.
- [ ] `M00-002` Registrare commit baseline e branch di lavoro nel file di stato.
- [ ] `M00-003` Inventariare tutti i file modificati preesistenti.
- [ ] `M00-004` Classificare ogni modifica come feature, fix, test, docs o artefatto.
- [ ] `M00-005` Separare le modifiche Oracle Autopilot dalle modifiche storiche.
- [ ] `M00-006` Rimuovere dalla working tree gli artefatti generati non necessari.
- [ ] `M00-007` Ignorare `tsconfig.tsbuildinfo` se non deve essere versionato.
- [ ] `M00-008` Ignorare database runtime locali non destinati al repository.
- [ ] `M00-009` Decidere se `.lean-ctx/overlays.json` deve essere versionato.
- [ ] `M00-010` Registrare lo spostamento dei vecchi phase plan come rename Git.
- [ ] `M00-011` Creare convenzione per commit atomici.
- [ ] `M00-012` Creare convenzione per branch milestone.
- [ ] `M00-013` Creare template per ADR.
- [ ] `M00-014` Creare template per milestone verification report.
- [ ] `M00-015` Creare template per incident report.
- [ ] `M00-016` Creare CODEOWNERS per core, risk, execution e integrations.
- [ ] `M00-017` Documentare i componenti che richiedono review di sicurezza.
- [ ] `M00-018` Documentare i componenti che richiedono review quantitativa.
- [ ] `M00-019` Documentare i componenti che richiedono verifica legale/firm rules.
- [ ] `M00-020` Verificare che il repository non contenga credenziali.
- [ ] `M00-021` Aggiungere secret scanning alla CI.
- [ ] `M00-022` Aggiungere dependency review alla CI.
- [ ] `M00-023` Aggiungere SBOM Python alla release pipeline.
- [ ] `M00-024` Aggiungere SBOM Node alla release pipeline.
- [ ] `M00-025` Pubblicare il report di chiusura M00.

## M01 — Baseline riproducibile

**Dipendenze:** M00.
**Exit gate:** build e test riproducibili su macchina pulita e CI.

- [x] `M01-001` Rendere verde la suite Python completa.
- [x] `M01-002` Rendere verde Ruff.
- [x] `M01-003` Rendere verde Ruff formatter.
- [x] `M01-004` Rendere verde mypy strict sui package applicativi.
- [x] `M01-005` Sincronizzare LightGBM nella virtualenv Python 3.12.
- [x] `M01-006` Verificare `uv lock --check`.
- [x] `M01-007` Rendere verde la build dashboard.
- [x] `M01-008` Rendere verdi i test dashboard.
- [x] `M01-009` Eseguire la suite completa nella CI Python.
- [x] `M01-010` Aggiungere typecheck, test e build del bridge Eliza alla CI.
- [ ] `M01-011` Correggere la configurazione Ruff isort/formatter incompatibile.
- [ ] `M01-012` Eliminare il warning Starlette/httpx2 nei test API.
- [ ] `M01-013` Correggere gli AsyncMock non awaited nel client NATS.
- [ ] `M01-014` Correggere i warning Pandas 4 su timestamp UTC.
- [ ] `M01-015` Correggere i warning LightGBM sui feature name.
- [ ] `M01-016` Classificare i warning NumPy degli operatori genetici.
- [ ] `M01-017` Definire un warning budget CI.
- [ ] `M01-018` Far fallire la CI quando il warning budget cresce.
- [ ] `M01-019` Aggiungere test d'installazione su ambiente vuoto.
- [ ] `M01-020` Aggiungere smoke test degli import principali.
- [ ] `M01-021` Verificare Python 3.12 come unica versione live supportata.
- [ ] `M01-022` Documentare Node supportato per dashboard.
- [ ] `M01-023` Documentare Node supportato per Eliza bridge.
- [ ] `M01-024` Verificare Docker build su runner pulito.
- [ ] `M01-025` Pubblicare il report di chiusura M01.

## M02 — Configurazione, segreti e ambienti

**Dipendenze:** M01.
**Exit gate:** configurazioni tipizzate e separate per replay, paper, shadow e live.

- [ ] `M02-001` Definire enum canonico degli ambienti operativi.
- [ ] `M02-002` Aggiungere profilo configurazione `replay`.
- [ ] `M02-003` Aggiungere profilo configurazione `paper`.
- [ ] `M02-004` Aggiungere profilo configurazione `shadow`.
- [ ] `M02-005` Aggiungere profilo configurazione `evaluation`.
- [ ] `M02-006` Aggiungere profilo configurazione `funded`.
- [ ] `M02-007` Impedire l'avvio live con configurazione debug.
- [ ] `M02-008` Impedire l'avvio live senza API authentication.
- [ ] `M02-009` Impedire l'avvio live con broker paper.
- [ ] `M02-010` Impedire l'avvio paper con credenziali funded.
- [ ] `M02-011` Definire schema tipizzato delle credenziali broker.
- [ ] `M02-012` Integrare un secrets manager locale per sviluppo.
- [ ] `M02-013` Definire interfaccia per secrets manager production.
- [ ] `M02-014` Eliminare password statiche dal Compose.
- [ ] `M02-015` Aggiungere rotazione delle API key Oracle.
- [ ] `M02-016` Aggiungere scope read-only per intelligence agents.
- [ ] `M02-017` Aggiungere scope execution per OMS soltanto.
- [ ] `M02-018` Aggiungere scope emergency per kill switch.
- [ ] `M02-019` Registrare hash della configurazione a ogni run.
- [ ] `M02-020` Aggiungere validazione startup fail-closed.
- [ ] `M02-021` Aggiungere test di configurazione mancante.
- [ ] `M02-022` Aggiungere test di credenziale errata.
- [ ] `M02-023` Aggiungere test di environment crossing.
- [ ] `M02-024` Documentare procedura di bootstrap ambiente.
- [ ] `M02-025` Pubblicare il report di chiusura M02.

---

# Programma B — Contratti di dominio e dati point-in-time

## M03 — Contratti Investment Committee

**Dipendenze:** M01.
**Exit gate:** ogni decisione portfolio ha schema, versione, scadenza e lineage.

- [x] `M03-001` Definire `TradingMode`.
- [x] `M03-002` Definire `CommitteeTrigger`.
- [x] `M03-003` Definire `ExecutionPreference`.
- [x] `M03-004` Definire `PositionTarget`.
- [x] `M03-005` Definire `PortfolioPlan`.
- [x] `M03-006` Definire `TradeIntent`.
- [x] `M03-007` Validare scadenza del PortfolioPlan.
- [x] `M03-008` Validare unicità dei target per strumento.
- [x] `M03-009` Compilare target in delta di posizione.
- [x] `M03-010` Classificare open/increase/reduce/close/reverse.
- [ ] `M03-011` Aggiungere versione dello schema PortfolioPlan.
- [ ] `M03-012` Aggiungere portfolio snapshot ID al PortfolioPlan.
- [ ] `M03-013` Aggiungere market snapshot ID al PortfolioPlan.
- [ ] `M03-014` Aggiungere rule-profile version al PortfolioPlan.
- [ ] `M03-015` Aggiungere decision supersession ID.
- [ ] `M03-016` Aggiungere campo `no_trade_reason`.
- [ ] `M03-017` Aggiungere target risk contribution.
- [ ] `M03-018` Aggiungere expected transaction cost.
- [ ] `M03-019` Aggiungere expected holding period.
- [ ] `M03-020` Aggiungere exit policy strutturata.
- [ ] `M03-021` Aggiungere schema hedge relationship.
- [ ] `M03-022` Aggiungere schema desk budget.
- [ ] `M03-023` Aggiungere migrazione schema v1→v2.
- [ ] `M03-024` Generare JSON Schema pubblicabile.
- [ ] `M03-025` Pubblicare il report di chiusura M03.

## M04 — Futures domain model

**Dipendenze:** M03.
**Exit gate:** prezzi, P&L e sizing usano unità reali per contratto.

- [ ] `M04-001` Definire `ContractSpec` canonico.
- [ ] `M04-002` Aggiungere exchange al ContractSpec.
- [ ] `M04-003` Aggiungere root symbol al ContractSpec.
- [ ] `M04-004` Aggiungere tradable contract symbol.
- [ ] `M04-005` Aggiungere multiplier.
- [ ] `M04-006` Aggiungere point value.
- [ ] `M04-007` Aggiungere tick size.
- [ ] `M04-008` Aggiungere tick value.
- [ ] `M04-009` Aggiungere currency.
- [ ] `M04-010` Aggiungere mini/micro equivalence ratio.
- [ ] `M04-011` Aggiungere initial margin.
- [ ] `M04-012` Aggiungere maintenance margin.
- [ ] `M04-013` Aggiungere settlement type.
- [ ] `M04-014` Aggiungere contract expiry.
- [ ] `M04-015` Aggiungere first notice date.
- [ ] `M04-016` Aggiungere last trade date.
- [ ] `M04-017` Creare catalogo ES/MES.
- [ ] `M04-018` Creare catalogo NQ/MNQ.
- [ ] `M04-019` Creare catalogo GC/MGC.
- [ ] `M04-020` Creare catalogo CL/MCL.
- [ ] `M04-021` Creare catalogo ZN/ZB.
- [ ] `M04-022` Creare catalogo 6E/M6E.
- [ ] `M04-023` Verificare P&L campione contro specifiche exchange.
- [ ] `M04-024` Eliminare ogni fallback generico di point value.
- [ ] `M04-025` Pubblicare il report di chiusura M04.

## M05 — Sessioni, calendari e contract roll

**Dipendenze:** M04.
**Exit gate:** ogni timestamp appartiene a una sessione verificata e ogni
contratto è tradabile alla data richiesta.

- [ ] `M05-001` Definire `TradingSession`.
- [ ] `M05-002` Definire timezone exchange.
- [ ] `M05-003` Definire maintenance break.
- [ ] `M05-004` Definire liquidation deadline.
- [ ] `M05-005` Definire early close.
- [ ] `M05-006` Integrare holiday calendar CME.
- [ ] `M05-007` Integrare holiday calendar ICE se necessario.
- [ ] `M05-008` Aggiungere test DST spring transition.
- [ ] `M05-009` Aggiungere test DST autumn transition.
- [ ] `M05-010` Aggiungere test holiday close.
- [ ] `M05-011` Aggiungere test early close.
- [ ] `M05-012` Definire roll policy volume-based.
- [ ] `M05-013` Definire roll policy calendar-based.
- [ ] `M05-014` Definire back-adjustment policy.
- [ ] `M05-015` Separare continuous symbol e tradable symbol.
- [ ] `M05-016` Aggiungere mapping continuous→contract.
- [ ] `M05-017` Aggiungere controllo expired contract.
- [ ] `M05-018` Aggiungere controllo first notice date.
- [ ] `M05-019` Aggiungere roll cost al backtest.
- [ ] `M05-020` Aggiungere roll event al bus.
- [ ] `M05-021` Aggiungere pre-roll portfolio review.
- [ ] `M05-022` Aggiungere auto-flatten prima della scadenza configurata.
- [ ] `M05-023` Verificare replay di una roll week.
- [ ] `M05-024` Documentare fonti dei calendari.
- [ ] `M05-025` Pubblicare il report di chiusura M05.

## M06 — Point-in-time data platform

**Dipendenze:** M01, M04.
**Exit gate:** nessun consumer può osservare dati non disponibili al tempo della
decisione.

- [x] `M06-001` Definire evidence reference con timestamp e hash.
- [x] `M06-002` Definire opportunity observation point-in-time.
- [x] `M06-003` Rifiutare availability precedente all'event time.
- [ ] `M06-004` Aggiungere `published_at` ai record esterni.
- [ ] `M06-005` Aggiungere `ingested_at` ai record esterni.
- [ ] `M06-006` Aggiungere `revision_id` ai record revisionabili.
- [ ] `M06-007` Aggiungere `source_license` ai dataset.
- [ ] `M06-008` Aggiungere `provider_version` alle cache key.
- [ ] `M06-009` Aggiungere contract alle cache key futures.
- [ ] `M06-010` Aggiungere adjustment version alle cache key.
- [ ] `M06-011` Persistire raw event prima della normalizzazione.
- [ ] `M06-012` Persistire normalized event separatamente.
- [ ] `M06-013` Creare data lineage raw→normalized→feature.
- [ ] `M06-014` Creare query `as_of` obbligatoria.
- [ ] `M06-015` Vietare query senza cutoff nei backtest.
- [ ] `M06-016` Aggiungere test di future-news leakage.
- [ ] `M06-017` Aggiungere test di macro revision leakage.
- [ ] `M06-018` Aggiungere test di filing availability.
- [ ] `M06-019` Aggiungere test di exchange timestamp ordering.
- [ ] `M06-020` Aggiungere duplicate detection.
- [ ] `M06-021` Aggiungere gap detection.
- [ ] `M06-022` Aggiungere outlier quarantine.
- [ ] `M06-023` Aggiungere provenance report per dataset.
- [ ] `M06-024` Certificare un dataset intraday futures.
- [ ] `M06-025` Pubblicare il report di chiusura M06.

## M07 — Real-time data ingestion

**Dipendenze:** M05, M06.
**Exit gate:** feed real-time monitorato, sequenziale e fail-closed.

- [ ] `M07-001` Selezionare provider futures real-time.
- [ ] `M07-002` Documentare licenza e limiti del provider.
- [ ] `M07-003` Implementare adapter quote.
- [ ] `M07-004` Implementare adapter trade.
- [ ] `M07-005` Implementare adapter bar.
- [ ] `M07-006` Implementare adapter order book se disponibile.
- [ ] `M07-007` Normalizzare timestamp exchange.
- [ ] `M07-008` Conservare sequence number.
- [ ] `M07-009` Rilevare sequence gap.
- [ ] `M07-010` Rilevare feed stale.
- [ ] `M07-011` Rilevare crossed market.
- [ ] `M07-012` Rilevare prezzo fuori tick.
- [ ] `M07-013` Rilevare contract mismatch.
- [ ] `M07-014` Implementare reconnect con backoff.
- [ ] `M07-015` Implementare snapshot recovery.
- [ ] `M07-016` Implementare replay dei messaggi persi.
- [ ] `M07-017` Pubblicare health event NATS.
- [ ] `M07-018` Bloccare nuove aperture su feed degraded.
- [ ] `M07-019` Preservare stop broker-side su feed degraded.
- [ ] `M07-020` Aggiungere metriche latency e gap.
- [ ] `M07-021` Aggiungere integration test disconnect.
- [ ] `M07-022` Aggiungere integration test duplicate tick.
- [ ] `M07-023` Aggiungere soak test di una sessione.
- [ ] `M07-024` Documentare runbook feed outage.
- [ ] `M07-025` Pubblicare il report di chiusura M07.

---

# Programma C — Intelligence alternativa ed ElizaOS

## M08 — ElizaOS security boundary

**Dipendenze:** M02, M06.
**Exit gate:** Eliza produce solo intelligence validata e non possiede capacità
di execution.

- [x] `M08-001` Creare package Eliza intelligence isolato.
- [x] `M08-002` Pin di `@elizaos/core`.
- [x] `M08-003` Definire schema Zod delle observation.
- [x] `M08-004` Creare safety-boundary provider.
- [x] `M08-005` Creare publish-observation action.
- [x] `M08-006` Creare HTTP publisher.
- [x] `M08-007` Creare gateway API Oracle.
- [x] `M08-008` Persistire observation in inbox SQLite.
- [x] `M08-009` Testare assenza di execution access.
- [x] `M08-010` Aggiungere bridge Eliza alla CI.
- [ ] `M08-011` Eliminare import type workaround interno a Eliza core.
- [ ] `M08-012` Creare compatibility test per upgrade Eliza.
- [ ] `M08-013` Creare allowlist dei plugin autorizzati.
- [ ] `M08-014` Creare denylist delle action sensibili.
- [ ] `M08-015` Bloccare wallet plugins nel runtime trading.
- [ ] `M08-016` Bloccare filesystem write non autorizzati.
- [ ] `M08-017` Bloccare network egress non autorizzato.
- [ ] `M08-018` Aggiungere per-plugin API credential scope.
- [ ] `M08-019` Aggiungere firma dell'observation envelope.
- [ ] `M08-020` Aggiungere replay protection.
- [ ] `M08-021` Aggiungere rate limit per agent.
- [ ] `M08-022` Aggiungere circuit breaker per plugin.
- [ ] `M08-023` Risolvere o accettare formalmente advisory npm low.
- [ ] `M08-024` Eseguire security review del bridge.
- [ ] `M08-025` Pubblicare il report di chiusura M08.

## M09 — Alternative intelligence scouts

**Dipendenze:** M08.
**Exit gate:** almeno tre scout producono observation verificabili in shadow.

- [ ] `M09-001` Definire interfaccia Scout Agent.
- [ ] `M09-002` Definire source credibility score.
- [ ] `M09-003` Definire novelty score.
- [ ] `M09-004` Definire corroboration score.
- [ ] `M09-005` Definire manipulation-risk score.
- [ ] `M09-006` Implementare News Event Scout.
- [ ] `M09-007` Implementare Social Narrative Scout.
- [ ] `M09-008` Implementare On-chain Flow Scout.
- [ ] `M09-009` Implementare Ecosystem/GitHub Scout.
- [ ] `M09-010` Implementare Cross-market Dislocation Scout.
- [ ] `M09-011` Implementare Liquidity Anomaly Scout.
- [ ] `M09-012` Implementare Regulatory Event Scout.
- [ ] `M09-013` Implementare Source Credibility Agent.
- [ ] `M09-014` Implementare observation deduplication.
- [ ] `M09-015` Implementare observation clustering.
- [ ] `M09-016` Implementare conflicting-observation detection.
- [ ] `M09-017` Implementare observation expiry.
- [ ] `M09-018` Implementare prompt-injection classifier.
- [ ] `M09-019` Implementare URL/domain allowlist.
- [ ] `M09-020` Collegare observation al feature store.
- [ ] `M09-021` Collegare observation all'Investment Committee.
- [ ] `M09-022` Creare dashboard source credibility.
- [ ] `M09-023` Eseguire shadow run di trenta sessioni.
- [ ] `M09-024` Misurare alpha incrementale netto degli scout.
- [ ] `M09-025` Pubblicare il report di chiusura M09.

---

# Programma D — LLM platform e Investment Committee

## M10 — LLM gateway production-grade

**Dipendenze:** M02.
**Exit gate:** ogni model call è versionata, limitata, osservabile e riproducibile.

- [ ] `M10-001` Definire model registry.
- [ ] `M10-002` Registrare provider e model version.
- [ ] `M10-003` Registrare prompt version.
- [ ] `M10-004` Registrare tool schema version.
- [ ] `M10-005` Registrare temperature e sampling params.
- [ ] `M10-006` Registrare token input/output.
- [ ] `M10-007` Registrare costo stimato.
- [ ] `M10-008` Registrare latency.
- [ ] `M10-009` Registrare timeout.
- [ ] `M10-010` Implementare retry policy per errore transient.
- [ ] `M10-011` Vietare retry su action non idempotente.
- [ ] `M10-012` Implementare provider circuit breaker.
- [ ] `M10-013` Implementare rate-limit budget.
- [ ] `M10-014` Implementare daily cost budget.
- [ ] `M10-015` Implementare fallback model policy.
- [ ] `M10-016` Implementare local-model fallback read-only.
- [ ] `M10-017` Implementare structured-output repair limitato.
- [ ] `M10-018` Implementare invalid-output fail-closed.
- [ ] `M10-019` Implementare prompt hash.
- [ ] `M10-020` Implementare context hash.
- [ ] `M10-021` Implementare tool-call audit.
- [ ] `M10-022` Aggiungere OpenTelemetry model spans.
- [ ] `M10-023` Aggiungere chaos test provider outage.
- [ ] `M10-024` Aggiungere model substitution test.
- [ ] `M10-025` Pubblicare il report di chiusura M10.

## M11 — Analyst desks

**Dipendenze:** M06, M10.
**Exit gate:** ogni desk ha input, blind spot, strumenti, output e test separati.

- [x] `M11-001` Consolidare Technical Analyst.
- [x] `M11-002` Consolidare Macro Analyst.
- [x] `M11-003` Consolidare Sentiment Analyst.
- [ ] `M11-004` Implementare Fundamental Analyst.
- [ ] `M11-005` Implementare News/Event Analyst.
- [ ] `M11-006` Implementare Market Microstructure Analyst.
- [ ] `M11-007` Implementare Volatility Analyst.
- [ ] `M11-008` Implementare Cross-asset Analyst.
- [ ] `M11-009` Implementare Futures Curve Analyst.
- [ ] `M11-010` Implementare Rates Desk.
- [ ] `M11-011` Implementare Equity Index Desk.
- [ ] `M11-012` Implementare FX Desk.
- [ ] `M11-013` Implementare Commodity Desk.
- [ ] `M11-014` Implementare Metals Desk.
- [ ] `M11-015` Implementare Crypto Proxy Desk.
- [ ] `M11-016` Definire blind spot per ogni desk.
- [ ] `M11-017` Definire tool allowlist per ogni desk.
- [ ] `M11-018` Definire latency budget per ogni desk.
- [ ] `M11-019` Definire confidence calibration per desk.
- [ ] `M11-020` Creare benchmark deterministico per desk.
- [ ] `M11-021` Aggiungere test point-in-time per desk.
- [ ] `M11-022` Aggiungere test conflicting inputs.
- [ ] `M11-023` Aggiungere test missing data.
- [ ] `M11-024` Aggiungere desk performance attribution.
- [ ] `M11-025` Pubblicare il report di chiusura M11.

## M12 — TradingAgents research council

**Dipendenze:** M11.
**Exit gate:** bull/bear e risk council producono report strutturati, limitati e
riproducibili.

- [x] `M12-001` Conservare debate team esistente.
- [ ] `M12-002` Definire Bull Thesis schema.
- [ ] `M12-003` Definire Bear Thesis schema.
- [ ] `M12-004` Definire Evidence Critic schema.
- [ ] `M12-005` Definire debate facilitator schema.
- [ ] `M12-006` Limitare round del debate.
- [ ] `M12-007` Limitare token del debate.
- [ ] `M12-008` Registrare disagreement map.
- [ ] `M12-009` Registrare unresolved assumptions.
- [ ] `M12-010` Registrare evidence cited.
- [ ] `M12-011` Rifiutare evidence ID inesistenti.
- [ ] `M12-012` Implementare risky risk reviewer.
- [ ] `M12-013` Implementare neutral risk reviewer.
- [ ] `M12-014` Implementare conservative risk reviewer.
- [ ] `M12-015` Implementare risk facilitator.
- [ ] `M12-016` Definire escalation a NO_TRADE.
- [ ] `M12-017` Definire escalation a human review per shadow.
- [ ] `M12-018` Aggiungere debate ablation test.
- [ ] `M12-019` Misurare costo marginale del debate.
- [ ] `M12-020` Misurare qualità marginale del debate.
- [ ] `M12-021` Aggiungere adversarial evidence test.
- [ ] `M12-022` Aggiungere prompt injection debate test.
- [ ] `M12-023` Aggiungere hallucinated citation test.
- [ ] `M12-024` Creare dashboard debate trace.
- [ ] `M12-025` Pubblicare il report di chiusura M12.

## M13 — Fund Manager e portfolio decisions

**Dipendenze:** M03, M12.
**Exit gate:** il Fund Manager può produrre target portfolio completi senza
accedere al broker.

- [x] `M13-001` Implementare LLM Fund Manager.
- [x] `M13-002` Usare output Pydantic strutturato.
- [x] `M13-003` Filtrare observation ID inventati.
- [x] `M13-004` Registrare modello e prompt version.
- [x] `M13-005` Supportare portfolio piatto.
- [ ] `M13-006` Inserire current ledger snapshot nel prompt.
- [ ] `M13-007` Inserire margin snapshot nel prompt.
- [ ] `M13-008` Inserire firm-rule summary nel prompt.
- [ ] `M13-009` Inserire desk budgets nel prompt.
- [ ] `M13-010` Inserire execution cost estimate nel prompt.
- [ ] `M13-011` Inserire correlation state nel prompt.
- [ ] `M13-012` Inserire open-order state nel prompt.
- [ ] `M13-013` Validare target contro tradable universe.
- [ ] `M13-014` Validare target contro expired contracts.
- [ ] `M13-015` Validare target integer contracts.
- [ ] `M13-016` Validare ogni target non-zero con invalidation.
- [ ] `M13-017` Validare ogni target non-zero con stop policy.
- [ ] `M13-018` Validare cash/margin buffer.
- [ ] `M13-019` Implementare plan supersession.
- [ ] `M13-020` Implementare plan cancellation.
- [ ] `M13-021` Implementare plan expiry worker.
- [ ] `M13-022` Aggiungere duplicate-plan test.
- [ ] `M13-023` Aggiungere stale-context test.
- [ ] `M13-024` Aggiungere live-mode permission test.
- [ ] `M13-025` Pubblicare il report di chiusura M13.

## M14 — QuantAgents memory e simulated feedback

**Dipendenze:** M06, M13.
**Exit gate:** decisioni ed esiti sono durevoli, ricercabili e valutabili senza
future leakage.

- [x] `M14-001` Creare decision journal SQLite.
- [x] `M14-002` Persistire PortfolioPlan.
- [x] `M14-003` Persistire DecisionOutcome.
- [x] `M14-004` Separare simulated reward e realized reward.
- [x] `M14-005` Calcolare dual reward sui feedback disponibili.
- [ ] `M14-006` Definire Market Information Memory.
- [ ] `M14-007` Definire Strategy Memory.
- [ ] `M14-008` Definire Report Memory.
- [ ] `M14-009` Definire Execution Memory.
- [ ] `M14-010` Definire Risk Incident Memory.
- [ ] `M14-011` Definire Source Credibility Memory.
- [ ] `M14-012` Aggiungere embedding metadata version.
- [ ] `M14-013` Aggiungere memory available_at.
- [ ] `M14-014` Vietare retrieval futuro.
- [ ] `M14-015` Implementare similarity retrieval.
- [ ] `M14-016` Implementare recency weighting.
- [ ] `M14-017` Implementare regime filtering.
- [ ] `M14-018` Implementare instrument filtering.
- [ ] `M14-019` Implementare source-quality filtering.
- [ ] `M14-020` Implementare memory invalidation.
- [ ] `M14-021` Implementare memory compaction.
- [ ] `M14-022` Migrare journal production a PostgreSQL.
- [ ] `M14-023` Aggiungere memory leakage test.
- [ ] `M14-024` Aggiungere corrupted-memory test.
- [ ] `M14-025` Pubblicare il report di chiusura M14.

## M15 — Meeting scheduler

**Dipendenze:** M12, M14.
**Exit gate:** meeting periodici ed event-driven sono deterministici e bounded.

- [ ] `M15-001` Definire Market Analysis Meeting.
- [ ] `M15-002` Definire Strategy Development Meeting.
- [ ] `M15-003` Definire Budget Allocation Conference.
- [ ] `M15-004` Definire Experience Sharing Conference.
- [ ] `M15-005` Definire Risk Alert Meeting.
- [ ] `M15-006` Definire Extreme Market Conference.
- [ ] `M15-007` Definire Post-trade Review.
- [ ] `M15-008` Definire daily compliance review.
- [ ] `M15-009` Configurare trigger temporali.
- [ ] `M15-010` Configurare trigger volatility.
- [ ] `M15-011` Configurare trigger drawdown.
- [ ] `M15-012` Configurare trigger correlation spike.
- [ ] `M15-013` Configurare trigger liquidity collapse.
- [ ] `M15-014` Configurare trigger news systemic.
- [ ] `M15-015` Configurare trigger broker degradation.
- [ ] `M15-016` Configurare max duration.
- [ ] `M15-017` Configurare max rounds.
- [ ] `M15-018` Configurare max token cost.
- [ ] `M15-019` Implementare meeting cancellation.
- [ ] `M15-020` Implementare meeting idempotency.
- [ ] `M15-021` Persistire meeting transcript strutturato.
- [ ] `M15-022` Aggiungere overlapping-meeting test.
- [ ] `M15-023` Aggiungere timeout test.
- [ ] `M15-024` Aggiungere emergency preemption test.
- [ ] `M15-025` Pubblicare il report di chiusura M15.

---

# Programma E — Ricerca, alpha e portfolio allocation

## M16 — Backtest integrity

**Dipendenze:** M04-M07.
**Exit gate:** risultati senza leakage, con costi, holdout e provenance.

- [x] `M16-001` Aggiungere prefix-invariance agli operatori genetici.
- [x] `M16-002` Rendere causali rank/scale/zscore/ts_mean.
- [ ] `M16-003` Verificare uso effettivo dei train indices.
- [ ] `M16-004` Implementare purge.
- [ ] `M16-005` Implementare embargo.
- [ ] `M16-006` Implementare nested walk-forward.
- [ ] `M16-007` Definire final holdout sigillato.
- [ ] `M16-008` Impedire accesso GA al final holdout.
- [ ] `M16-009` Versionare dataset split.
- [ ] `M16-010` Aggiungere commissioni per contratto.
- [ ] `M16-011` Aggiungere exchange fees.
- [ ] `M16-012` Aggiungere slippage model.
- [ ] `M16-013` Aggiungere roll cost.
- [ ] `M16-014` Aggiungere bid/ask execution.
- [ ] `M16-015` Aggiungere intraday unrealized equity.
- [ ] `M16-016` Rendere sizing identico paper/backtest.
- [ ] `M16-017` Creare cross-engine parity suite.
- [ ] `M16-018` Selezionare motore canonico live-parity.
- [ ] `M16-019` Aggiungere random-entry benchmark.
- [ ] `M16-020` Aggiungere trend benchmark.
- [ ] `M16-021` Aggiungere buy-and-hold benchmark.
- [ ] `M16-022` Aggiungere survivorship-bias test.
- [ ] `M16-023` Aggiungere look-ahead audit automatico.
- [ ] `M16-024` Generare backtest provenance manifest.
- [ ] `M16-025` Pubblicare il report di chiusura M16.

## M17 — Alpha research pipeline

**Dipendenze:** M09, M16.
**Exit gate:** ogni edge è incrementale, netto dei costi e replicabile OOS.

- [ ] `M17-001` Definire AlphaHypothesis schema.
- [ ] `M17-002` Definire hypothesis owner.
- [ ] `M17-003` Definire economic rationale.
- [ ] `M17-004` Definire expected horizon.
- [ ] `M17-005` Definire decay expectation.
- [ ] `M17-006` Definire falsification condition.
- [ ] `M17-007` Definire baseline competitor.
- [ ] `M17-008` Definire transaction-cost threshold.
- [ ] `M17-009` Eseguire in-sample experiment.
- [ ] `M17-010` Eseguire walk-forward experiment.
- [ ] `M17-011` Eseguire final holdout experiment.
- [ ] `M17-012` Eseguire regime attribution.
- [ ] `M17-013` Eseguire factor attribution.
- [ ] `M17-014` Eseguire turnover attribution.
- [ ] `M17-015` Eseguire execution-cost attribution.
- [ ] `M17-016` Eseguire capacity estimate.
- [ ] `M17-017` Eseguire correlation-to-existing-alpha test.
- [ ] `M17-018` Eseguire bootstrap confidence interval.
- [ ] `M17-019` Eseguire multiple-testing correction.
- [ ] `M17-020` Assegnare status reject/research/paper/live.
- [ ] `M17-021` Creare alpha registry.
- [ ] `M17-022` Creare alpha retirement rule.
- [ ] `M17-023` Creare online decay monitor.
- [ ] `M17-024` Creare post-mortem per alpha ritirato.
- [ ] `M17-025` Pubblicare il report di chiusura M17.

## M18 — HedgeAgents allocation engine

**Dipendenze:** M04, M13, M16.
**Exit gate:** budget multi-desk ottimizzato e limitato da rischio e costi.

- [x] `M18-001` Implementare optimizer expected-return/covariance/CVaR.
- [x] `M18-002` Implementare desk weight caps.
- [x] `M18-003` Testare preferenza risk-adjusted.
- [ ] `M18-004` Definire expected-return input contract.
- [ ] `M18-005` Definire covariance input contract.
- [ ] `M18-006` Definire CVaR input contract.
- [ ] `M18-007` Definire liquidity penalty.
- [ ] `M18-008` Definire transaction-cost penalty.
- [ ] `M18-009` Definire margin penalty.
- [ ] `M18-010` Definire concentration penalty.
- [ ] `M18-011` Definire turnover penalty.
- [ ] `M18-012` Definire minimum hedge budget.
- [ ] `M18-013` Definire cash buffer constraint.
- [ ] `M18-014` Supportare long/short constraints.
- [ ] `M18-015` Supportare contract integer rounding.
- [ ] `M18-016` Verificare feasibility dopo rounding.
- [ ] `M18-017` Implementare fallback allocation conservativa.
- [ ] `M18-018` Implementare covariance shrinkage.
- [ ] `M18-019` Implementare stressed covariance.
- [ ] `M18-020` Implementare correlation spike response.
- [ ] `M18-021` Aggiungere optimizer property tests.
- [ ] `M18-022` Aggiungere infeasible-constraints test.
- [ ] `M18-023` Aggiungere numerical-stability test.
- [ ] `M18-024` Collegare optimizer al Fund Manager toolset.
- [ ] `M18-025` Pubblicare il report di chiusura M18.

---

# Programma F — Ledger, OMS e broker

## M19 — Account ledger durevole

**Dipendenze:** M04.
**Exit gate:** balance, equity, P&L, margin e posizioni sopravvivono ai restart e
sono riconciliabili.

- [ ] `M19-001` Definire AccountSnapshot.
- [ ] `M19-002` Definire BalanceSnapshot.
- [ ] `M19-003` Definire EquitySnapshot.
- [ ] `M19-004` Definire PositionSnapshot.
- [ ] `M19-005` Definire MarginSnapshot.
- [ ] `M19-006` Definire CashMovement.
- [ ] `M19-007` Definire CommissionEvent.
- [ ] `M19-008` Definire RealizedPnLEvent.
- [ ] `M19-009` Definire UnrealizedPnLEvent.
- [ ] `M19-010` Definire daily opening equity.
- [ ] `M19-011` Definire peak equity.
- [ ] `M19-012` Definire authoritative sequence number.
- [ ] `M19-013` Creare schema PostgreSQL ledger.
- [ ] `M19-014` Creare migration ledger iniziale.
- [ ] `M19-015` Implementare append-only ledger writer.
- [ ] `M19-016` Implementare account state projector.
- [ ] `M19-017` Implementare position projector.
- [ ] `M19-018` Implementare realized P&L calculator.
- [ ] `M19-019` Implementare unrealized P&L calculator.
- [ ] `M19-020` Implementare commission accounting.
- [ ] `M19-021` Implementare margin accounting.
- [ ] `M19-022` Aggiungere partial-fill invariant tests.
- [ ] `M19-023` Aggiungere reversal invariant tests.
- [ ] `M19-024` Aggiungere restart recovery test.
- [ ] `M19-025` Pubblicare il report di chiusura M19.

## M20 — Durable OMS

**Dipendenze:** M19.
**Exit gate:** order intent, order, ack, fill, amend e cancel sono persistenti e
idempotenti.

- [x] `M20-001` Usare intent ID come request idempotency key.
- [x] `M20-002` Impedire shadow/replay order request.
- [x] `M20-003` Tradurre TradeIntent in OrderRequest.
- [ ] `M20-004` Definire OrderIntentRecord.
- [ ] `M20-005` Definire BrokerOrderRecord.
- [ ] `M20-006` Definire FillRecord.
- [ ] `M20-007` Definire CancelRecord.
- [ ] `M20-008` Definire AmendRecord.
- [ ] `M20-009` Definire RejectRecord.
- [ ] `M20-010` Creare schema PostgreSQL OMS.
- [ ] `M20-011` Persistire intent prima del submit.
- [ ] `M20-012` Persistire broker ack.
- [ ] `M20-013` Persistire reject.
- [ ] `M20-014` Persistire partial fill.
- [ ] `M20-015` Persistire full fill.
- [ ] `M20-016` Persistire cancel.
- [ ] `M20-017` Persistire amend.
- [ ] `M20-018` Recuperare request idempotency dopo restart.
- [ ] `M20-019` Recuperare open orders dopo restart.
- [ ] `M20-020` Recuperare pending cancels dopo restart.
- [ ] `M20-021` Gestire duplicate broker event.
- [ ] `M20-022` Gestire out-of-order broker event.
- [ ] `M20-023` Gestire unknown broker order.
- [ ] `M20-024` Aggiungere crash-between-intent-and-submit test.
- [ ] `M20-025` Pubblicare il report di chiusura M20.

## M21 — Reconciliation

**Dipendenze:** M19, M20.
**Exit gate:** broker, OMS e ledger convergono o il sistema si blocca.

- [ ] `M21-001` Definire reconciliation snapshot.
- [ ] `M21-002` Definire position mismatch.
- [ ] `M21-003` Definire order mismatch.
- [ ] `M21-004` Definire fill mismatch.
- [ ] `M21-005` Definire cash mismatch.
- [ ] `M21-006` Definire margin mismatch.
- [ ] `M21-007` Implementare startup reconciliation.
- [ ] `M21-008` Implementare periodic reconciliation.
- [ ] `M21-009` Implementare post-fill reconciliation.
- [ ] `M21-010` Implementare post-reconnect reconciliation.
- [ ] `M21-011` Importare broker open orders.
- [ ] `M21-012` Importare broker positions.
- [ ] `M21-013` Importare broker executions.
- [ ] `M21-014` Importare broker account values.
- [ ] `M21-015` Classificare mismatch recoverable.
- [ ] `M21-016` Classificare mismatch fatal.
- [ ] `M21-017` Bloccare aperture su mismatch.
- [ ] `M21-018` Preservare flatten capability su mismatch.
- [ ] `M21-019` Aggiungere orphan-order test.
- [ ] `M21-020` Aggiungere missing-fill test.
- [ ] `M21-021` Aggiungere duplicate-fill test.
- [ ] `M21-022` Aggiungere position-drift test.
- [ ] `M21-023` Aggiungere reconnect convergence test.
- [ ] `M21-024` Creare reconciliation dashboard.
- [ ] `M21-025` Pubblicare il report di chiusura M21.

## M22 — Broker e prop-platform adapters

**Dipendenze:** M20, M21.
**Exit gate:** un adapter certificato copre l'intero lifecycle in sandbox/paper.

- [ ] `M22-001` Selezionare prima firm/program/platform.
- [ ] `M22-002` Verificare ufficialmente automazione consentita.
- [ ] `M22-003` Verificare ufficialmente API disponibile.
- [ ] `M22-004` Verificare ambiente sandbox/paper.
- [ ] `M22-005` Definire BrokerCapabilities.
- [ ] `M22-006` Definire market-order capability.
- [ ] `M22-007` Definire limit-order capability.
- [ ] `M22-008` Definire stop-order capability.
- [ ] `M22-009` Definire bracket/OCO capability.
- [ ] `M22-010` Definire amend capability.
- [ ] `M22-011` Definire streaming-order capability.
- [ ] `M22-012` Definire streaming-position capability.
- [ ] `M22-013` Implementare authentication.
- [ ] `M22-014` Implementare connection lifecycle.
- [ ] `M22-015` Implementare order submit.
- [ ] `M22-016` Implementare cancel.
- [ ] `M22-017` Implementare amend.
- [ ] `M22-018` Implementare execution stream.
- [ ] `M22-019` Implementare position stream.
- [ ] `M22-020` Implementare account stream.
- [ ] `M22-021` Implementare reconnect.
- [ ] `M22-022` Implementare heartbeat.
- [ ] `M22-023` Eseguire broker conformance suite.
- [ ] `M22-024` Eseguire sandbox soak test.
- [ ] `M22-025` Pubblicare il report di chiusura M22.

---

# Programma G — Prop-firm compliance e hard risk

## M23 — Versioned prop-firm rule catalog

**Dipendenze:** M02.
**Exit gate:** almeno un programma è modellato da fonti ufficiali e fail-closed.

- [x] `M23-001` Definire FirmProgramProfile.
- [x] `M23-002` Definire SupportMode.
- [x] `M23-003` Definire version key.
- [x] `M23-004` Definire source URL e checked-at.
- [x] `M23-005` Definire profile content hash.
- [x] `M23-006` Definire static/trailing drawdown modes.
- [x] `M23-007` Definire daily loss basis.
- [x] `M23-008` Definire contract cap.
- [x] `M23-009` Definire scaling plan.
- [x] `M23-010` Definire news blackout.
- [ ] `M23-011` Aggiungere account vintage.
- [ ] `M23-012` Aggiungere effective-to enforcement.
- [ ] `M23-013` Aggiungere source document snapshot.
- [ ] `M23-014` Aggiungere source hash verification job.
- [ ] `M23-015` Aggiungere automation policy details.
- [ ] `M23-016` Aggiungere copy-trading policy.
- [ ] `M23-017` Aggiungere prohibited-strategy policy.
- [ ] `M23-018` Aggiungere consistency variants.
- [ ] `M23-019` Aggiungere winning-day threshold.
- [ ] `M23-020` Aggiungere payout/scaling restrictions.
- [ ] `M23-021` Completare golden fixtures ufficiali.
- [ ] `M23-022` Aggiungere snapshot test per account size.
- [ ] `M23-023` Aggiungere expired-profile fail-closed test.
- [ ] `M23-024` Selezionare il primo profilo AUTO_SUPPORTED.
- [ ] `M23-025` Pubblicare il report di chiusura M23.

## M24 — Hard risk kernel

**Dipendenze:** M04, M05, M19, M23.
**Exit gate:** nessun ordine può superare un hard limit.

- [x] `M24-001` Collegare governor all'OrderManager.
- [x] `M24-002` Fail-closed senza contract specification.
- [x] `M24-003` Fail-closed senza protective stop.
- [x] `M24-004` Applicare support mode.
- [x] `M24-005` Applicare per-trade risk budget.
- [x] `M24-006` Applicare contract cap base.
- [ ] `M24-007` Applicare mini-equivalent conversion.
- [ ] `M24-008` Applicare current-position exposure.
- [ ] `M24-009` Applicare pending-order exposure.
- [ ] `M24-010` Applicare max concurrent positions.
- [ ] `M24-011` Applicare concentration limits.
- [ ] `M24-012` Applicare correlated exposure limits.
- [ ] `M24-013` Applicare margin buffer.
- [ ] `M24-014` Applicare daily loss continuous.
- [ ] `M24-015` Applicare trailing drawdown continuous.
- [ ] `M24-016` Applicare news blackout.
- [ ] `M24-017` Applicare session gate.
- [ ] `M24-018` Applicare overnight/weekend gate.
- [ ] `M24-019` Applicare liquidation deadline.
- [ ] `M24-020` Applicare stale-data gate.
- [ ] `M24-021` Applicare reconciliation gate.
- [ ] `M24-022` Applicare clock-drift gate.
- [ ] `M24-023` Aggiungere property test su tutti i limiti.
- [ ] `M24-024` Aggiungere bypass-path audit CLI/API/MAS.
- [ ] `M24-025` Pubblicare il report di chiusura M24.

## M25 — Kill switch e emergency controls

**Dipendenze:** M21, M22, M24.
**Exit gate:** cancel e flatten verificati broker-side in ogni failure mode.

- [ ] `M25-001` Definire kill-switch state machine.
- [ ] `M25-002` Definire global pause.
- [ ] `M25-003` Definire strategy pause.
- [ ] `M25-004` Definire instrument pause.
- [ ] `M25-005` Definire firm/account pause.
- [ ] `M25-006` Definire cancel-all command.
- [ ] `M25-007` Definire flatten-all command.
- [ ] `M25-008` Definire flatten-instrument command.
- [ ] `M25-009` Implementare broker-side cancel verification.
- [ ] `M25-010` Implementare broker-side flat verification.
- [ ] `M25-011` Implementare retry bounded.
- [ ] `M25-012` Implementare secondary notification channel.
- [ ] `M25-013` Implementare manual hardware-independent trigger.
- [ ] `M25-014` Implementare API emergency auth scope.
- [ ] `M25-015` Persistire kill-switch event.
- [ ] `M25-016` Bloccare auto-resume.
- [ ] `M25-017` Richiedere explicit recovery checklist.
- [ ] `M25-018` Aggiungere data-feed outage drill.
- [ ] `M25-019` Aggiungere broker-disconnect drill.
- [ ] `M25-020` Aggiungere LLM-outage drill.
- [ ] `M25-021` Aggiungere ledger-drift drill.
- [ ] `M25-022` Aggiungere runaway-order drill.
- [ ] `M25-023` Aggiungere partial-flatten drill.
- [ ] `M25-024` Documentare emergency runbook.
- [ ] `M25-025` Pubblicare il report di chiusura M25.

---

# Programma H — Execution intelligence e simulazione

## M26 — Execution Agent

**Dipendenze:** M07, M20, M24.
**Exit gate:** l'LLM sceglie execution preference entro limiti deterministici.

- [ ] `M26-001` Definire ExecutionContext.
- [ ] `M26-002` Definire spread snapshot.
- [ ] `M26-003` Definire liquidity snapshot.
- [ ] `M26-004` Definire volatility snapshot.
- [ ] `M26-005` Definire order urgency.
- [ ] `M26-006` Definire max slippage.
- [ ] `M26-007` Definire passive-limit policy.
- [ ] `M26-008` Definire marketable-limit policy.
- [ ] `M26-009` Definire TWAP policy.
- [ ] `M26-010` Definire VWAP policy.
- [ ] `M26-011` Definire order slicing.
- [ ] `M26-012` Definire limit chase bounds.
- [ ] `M26-013` Definire cancel/replace budget.
- [ ] `M26-014` Implementare LLM Execution Agent.
- [ ] `M26-015` Validare output contro broker capabilities.
- [ ] `M26-016` Validare output contro session state.
- [ ] `M26-017` Validare output contro price bands.
- [ ] `M26-018` Validare output contro tick size.
- [ ] `M26-019` Registrare execution rationale.
- [ ] `M26-020` Registrare expected fill quality.
- [ ] `M26-021` Calcolare implementation shortfall.
- [ ] `M26-022` Calcolare adverse selection.
- [ ] `M26-023` Aggiungere execution ablation test.
- [ ] `M26-024` Aggiungere stale-book test.
- [ ] `M26-025` Pubblicare il report di chiusura M26.

## M27 — Realistic paper broker

**Dipendenze:** M04, M07, M20.
**Exit gate:** paper fill model sufficient per confrontare shadow e live.

- [ ] `M27-001` Modellare bid/ask spread.
- [ ] `M27-002` Modellare latency.
- [ ] `M27-003` Modellare queue position.
- [ ] `M27-004` Modellare partial fill.
- [ ] `M27-005` Modellare fill probability.
- [ ] `M27-006` Modellare market impact.
- [ ] `M27-007` Modellare adverse selection.
- [ ] `M27-008` Modellare exchange reject.
- [ ] `M27-009` Modellare price-band reject.
- [ ] `M27-010` Modellare session reject.
- [ ] `M27-011` Modellare disconnect.
- [ ] `M27-012` Modellare delayed ack.
- [ ] `M27-013` Modellare duplicate execution event.
- [ ] `M27-014` Modellare out-of-order execution event.
- [ ] `M27-015` Modellare commissioni reali.
- [ ] `M27-016` Modellare exchange fees reali.
- [ ] `M27-017` Modellare overnight margin.
- [ ] `M27-018` Modellare forced liquidation.
- [ ] `M27-019` Calibrare modello su broker sandbox.
- [ ] `M27-020` Confrontare simulated vs observed fills.
- [ ] `M27-021` Definire parity tolerance.
- [ ] `M27-022` Aggiungere deterministic seed.
- [ ] `M27-023` Aggiungere stress scenario library.
- [ ] `M27-024` Eseguire paper-broker conformance suite.
- [ ] `M27-025` Pubblicare il report di chiusura M27.

---

# Programma I — Operazioni, sicurezza e osservabilità

## M28 — Service architecture e deployment

**Dipendenze:** M02, M19-M22.
**Exit gate:** stack completo avviabile, health-checked e aggiornabile.

- [ ] `M28-001` Definire market-data service.
- [ ] `M28-002` Definire intelligence service.
- [ ] `M28-003` Definire agent-orchestrator service.
- [ ] `M28-004` Definire portfolio service.
- [ ] `M28-005` Definire risk service.
- [ ] `M28-006` Definire OMS service.
- [ ] `M28-007` Definire ledger service.
- [ ] `M28-008` Definire broker-adapter service.
- [ ] `M28-009` Definire reconciliation worker.
- [ ] `M28-010` Definire scheduler service.
- [ ] `M28-011` Aggiungere servizi applicativi al Compose.
- [ ] `M28-012` Aggiungere healthcheck per servizio.
- [ ] `M28-013` Aggiungere readiness check per servizio.
- [ ] `M28-014` Aggiungere startup dependency check.
- [ ] `M28-015` Aggiungere graceful shutdown.
- [ ] `M28-016` Aggiungere rolling restart policy.
- [ ] `M28-017` Aggiungere database migration job.
- [ ] `M28-018` Aggiungere backup job.
- [ ] `M28-019` Aggiungere restore test.
- [ ] `M28-020` Aggiungere NTP/clock health check.
- [ ] `M28-021` Aggiungere resource limits.
- [ ] `M28-022` Aggiungere network segmentation.
- [ ] `M28-023` Eseguire clean-machine deploy test.
- [ ] `M28-024` Documentare deployment runbook.
- [ ] `M28-025` Pubblicare il report di chiusura M28.

## M29 — Observability e audit

**Dipendenze:** M10, M19-M22, M28.
**Exit gate:** ogni decisione e side effect è tracciabile end-to-end.

- [ ] `M29-001` Definire trace ID globale.
- [ ] `M29-002` Propagare trace ID data→decision.
- [ ] `M29-003` Propagare trace ID decision→intent.
- [ ] `M29-004` Propagare trace ID intent→order.
- [ ] `M29-005` Propagare trace ID order→fill.
- [ ] `M29-006` Propagare trace ID fill→ledger.
- [ ] `M29-007` Esportare OpenTelemetry traces.
- [ ] `M29-008` Esportare Prometheus metrics.
- [ ] `M29-009` Centralizzare log in Loki.
- [ ] `M29-010` Creare dashboard account health.
- [ ] `M29-011` Creare dashboard risk limits.
- [ ] `M29-012` Creare dashboard OMS health.
- [ ] `M29-013` Creare dashboard reconciliation.
- [ ] `M29-014` Creare dashboard LLM cost/latency.
- [ ] `M29-015` Creare dashboard alpha attribution.
- [ ] `M29-016` Creare alert daily-loss proximity.
- [ ] `M29-017` Creare alert drawdown proximity.
- [ ] `M29-018` Creare alert stale feed.
- [ ] `M29-019` Creare alert broker disconnect.
- [ ] `M29-020` Creare alert reconciliation mismatch.
- [ ] `M29-021` Creare alert LLM provider outage.
- [ ] `M29-022` Creare immutable audit export.
- [ ] `M29-023` Verificare audit replay di un trade.
- [ ] `M29-024` Documentare alert response matrix.
- [ ] `M29-025` Pubblicare il report di chiusura M29.

## M30 — Security hardening

**Dipendenze:** M28, M29.
**Exit gate:** threat model chiuso e nessun finding high/critical aperto.

- [ ] `M30-001` Creare threat model data plane.
- [ ] `M30-002` Creare threat model LLM plane.
- [ ] `M30-003` Creare threat model execution plane.
- [ ] `M30-004` Creare threat model Eliza plugins.
- [ ] `M30-005` Creare threat model broker credentials.
- [ ] `M30-006` Implementare least-privilege service accounts.
- [ ] `M30-007` Implementare API RBAC.
- [ ] `M30-008` Implementare credential rotation.
- [ ] `M30-009` Implementare encrypted backups.
- [ ] `M30-010` Implementare database TLS.
- [ ] `M30-011` Implementare service-to-service auth.
- [ ] `M30-012` Implementare signed config artifacts.
- [ ] `M30-013` Implementare signed rule profiles.
- [ ] `M30-014` Implementare dependency pinning policy.
- [ ] `M30-015` Implementare container image scanning.
- [ ] `M30-016` Implementare runtime filesystem read-only.
- [ ] `M30-017` Implementare outbound egress policy.
- [ ] `M30-018` Testare prompt injection.
- [ ] `M30-019` Testare data poisoning.
- [ ] `M30-020` Testare replay attack.
- [ ] `M30-021` Testare credential theft containment.
- [ ] `M30-022` Eseguire penetration test interno.
- [ ] `M30-023` Chiudere finding high/critical.
- [ ] `M30-024` Documentare security incident runbook.
- [ ] `M30-025` Pubblicare il report di chiusura M30.

---

# Programma J — Qualificazione e rollout

## M31 — Historical replay qualification

**Dipendenze:** M16-M18, M24, M27.
**Exit gate:** il sistema completo opera su replay senza leakage e senza bypass.

- [ ] `M31-001` Selezionare periodi bull.
- [ ] `M31-002` Selezionare periodi bear.
- [ ] `M31-003` Selezionare periodi sideways.
- [ ] `M31-004` Selezionare periodi high volatility.
- [ ] `M31-005` Selezionare periodi liquidity shock.
- [ ] `M31-006` Selezionare periodi macro surprise.
- [ ] `M31-007` Eseguire replay senza Eliza scouts.
- [ ] `M31-008` Eseguire replay con Eliza scouts.
- [ ] `M31-009` Eseguire replay senza debate.
- [ ] `M31-010` Eseguire replay con debate.
- [ ] `M31-011` Eseguire replay con Fund Manager baseline.
- [ ] `M31-012` Eseguire replay con Fund Manager challenger.
- [ ] `M31-013` Misurare return netto.
- [ ] `M31-014` Misurare Sharpe/Sortino/Calmar.
- [ ] `M31-015` Misurare max drawdown.
- [ ] `M31-016` Misurare prop-rule breaches.
- [ ] `M31-017` Misurare turnover.
- [ ] `M31-018` Misurare execution cost.
- [ ] `M31-019` Misurare model cost.
- [ ] `M31-020` Misurare decision latency.
- [ ] `M31-021` Eseguire factor attribution.
- [ ] `M31-022` Eseguire luck-vs-skill analysis.
- [ ] `M31-023` Definire qualification thresholds.
- [ ] `M31-024` Approvare o respingere replay gate.
- [ ] `M31-025` Pubblicare il report di chiusura M31.

## M32 — Live paper trading

**Dipendenze:** M07, M21-M31.
**Exit gate:** almeno sessanta sessioni paper senza incidente hard non gestito.

- [ ] `M32-001` Creare account paper dedicato.
- [ ] `M32-002` Verificare feed live paper.
- [ ] `M32-003` Verificare broker clock.
- [ ] `M32-004` Verificare ledger bootstrap.
- [ ] `M32-005` Verificare OMS bootstrap.
- [ ] `M32-006` Verificare reconciliation startup.
- [ ] `M32-007` Eseguire prima sessione read-only.
- [ ] `M32-008` Eseguire prima sessione con segnali.
- [ ] `M32-009` Eseguire prima sessione con ordini paper.
- [ ] `M32-010` Verificare stop e bracket.
- [ ] `M32-011` Verificare session flatten.
- [ ] `M32-012` Verificare daily rollover.
- [ ] `M32-013` Verificare restart intraday.
- [ ] `M32-014` Verificare reconnect intraday.
- [ ] `M32-015` Verificare LLM provider outage.
- [ ] `M32-016` Verificare Eliza outage.
- [ ] `M32-017` Verificare stale feed response.
- [ ] `M32-018` Verificare risk alert response.
- [ ] `M32-019` Verificare extreme-market conference.
- [ ] `M32-020` Misurare paper fill realism.
- [ ] `M32-021` Misurare decision stability.
- [ ] `M32-022` Misurare alpha decay.
- [ ] `M32-023` Completare sessanta sessioni.
- [ ] `M32-024` Approvare o respingere paper gate.
- [ ] `M32-025` Pubblicare il report di chiusura M32.

## M33 — Shadow trading su broker reale

**Dipendenze:** M32.
**Exit gate:** Oracle osserva account e mercato reali senza inviare ordini.

- [ ] `M33-001` Creare credenziali broker read-only.
- [ ] `M33-002` Bloccare submit nel broker adapter shadow.
- [ ] `M33-003` Importare posizioni reali read-only.
- [ ] `M33-004` Importare ordini reali read-only.
- [ ] `M33-005` Importare account values read-only.
- [ ] `M33-006` Generare shadow TradeIntent.
- [ ] `M33-007` Simulare shadow fills.
- [ ] `M33-008` Stimare achievable fills.
- [ ] `M33-009` Confrontare paper e shadow spread.
- [ ] `M33-010` Confrontare paper e shadow latency.
- [ ] `M33-011` Confrontare paper e shadow slippage.
- [ ] `M33-012` Verificare prop limits read-only.
- [ ] `M33-013` Verificare session rules read-only.
- [ ] `M33-014` Verificare news rules read-only.
- [ ] `M33-015` Eseguire restart recovery.
- [ ] `M33-016` Eseguire broker disconnect drill.
- [ ] `M33-017` Eseguire data disagreement drill.
- [ ] `M33-018` Eseguire kill-switch dry run.
- [ ] `M33-019` Completare trenta sessioni shadow.
- [ ] `M33-020` Calcolare live-parity error.
- [ ] `M33-021` Calcolare expected violation probability.
- [ ] `M33-022` Calcolare expected challenge value.
- [ ] `M33-023` Chiudere parity gaps.
- [ ] `M33-024` Approvare o respingere shadow gate.
- [ ] `M33-025` Pubblicare il report di chiusura M33.

## M34 — Prop evaluation rollout

**Dipendenze:** M23-M25, M33.
**Exit gate:** una evaluation completata senza violazioni software.

- [ ] `M34-001` Congelare firm/program/profile version.
- [ ] `M34-002` Congelare broker adapter version.
- [ ] `M34-003` Congelare model registry version.
- [ ] `M34-004` Congelare strategy set.
- [ ] `M34-005` Congelare risk configuration.
- [ ] `M34-006` Creare evaluation account.
- [ ] `M34-007` Verificare account rules con fonte ufficiale.
- [ ] `M34-008` Verificare automation permission.
- [ ] `M34-009` Verificare product allowlist.
- [ ] `M34-010` Eseguire preflight checklist.
- [ ] `M34-011` Abilitare evaluation mode.
- [ ] `M34-012` Monitorare ogni sessione.
- [ ] `M34-013` Eseguire daily reconciliation review.
- [ ] `M34-014` Eseguire daily risk review.
- [ ] `M34-015` Eseguire daily model review.
- [ ] `M34-016` Bloccare configurazione durante sessione.
- [ ] `M34-017` Registrare ogni manual intervention.
- [ ] `M34-018` Gestire eventuale rule change.
- [ ] `M34-019` Gestire eventuale platform outage.
- [ ] `M34-020` Gestire eventuale strategy pause.
- [ ] `M34-021` Completare evaluation o stop condition.
- [ ] `M34-022` Separare software breach da market loss.
- [ ] `M34-023` Eseguire evaluation post-mortem.
- [ ] `M34-024` Approvare o respingere funded promotion.
- [ ] `M34-025` Pubblicare il report di chiusura M34.

## M35 — Funded account limited rollout

**Dipendenze:** M34.
**Exit gate:** account funded operato con size minima e nessun incidente hard.

- [ ] `M35-001` Verificare funded rule differences.
- [ ] `M35-002` Creare funded profile version.
- [ ] `M35-003` Definire minimum size cap.
- [ ] `M35-004` Definire minimum daily risk cap.
- [ ] `M35-005` Definire funded kill threshold.
- [ ] `M35-006` Definire payout-aware buffer.
- [ ] `M35-007` Definire scaling freeze period.
- [ ] `M35-008` Eseguire funded preflight.
- [ ] `M35-009` Abilitare un solo account.
- [ ] `M35-010` Abilitare un solo strategy set.
- [ ] `M35-011` Abilitare un universe ristretto.
- [ ] `M35-012` Eseguire prima funded session.
- [ ] `M35-013` Verificare primo funded fill.
- [ ] `M35-014` Verificare primo funded close.
- [ ] `M35-015` Verificare daily reset.
- [ ] `M35-016` Verificare trailing drawdown.
- [ ] `M35-017` Verificare session flatten.
- [ ] `M35-018` Completare venti sessioni minimum-size.
- [ ] `M35-019` Eseguire funded performance attribution.
- [ ] `M35-020` Eseguire funded execution attribution.
- [ ] `M35-021` Eseguire funded incident review.
- [ ] `M35-022` Verificare payout eligibility.
- [ ] `M35-023` Approvare o respingere scaling.
- [ ] `M35-024` Aggiornare support matrix.
- [ ] `M35-025` Pubblicare il report di chiusura M35.

## M36 — Scaling e multi-account

**Dipendenze:** M35.
**Exit gate:** scaling limitato, misurabile e reversibile.

- [ ] `M36-001` Definire scaling policy.
- [ ] `M36-002` Definire de-scaling policy.
- [ ] `M36-003` Definire account-level risk budget.
- [ ] `M36-004` Definire global risk budget.
- [ ] `M36-005` Definire correlated-account exposure.
- [ ] `M36-006` Definire firm concentration cap.
- [ ] `M36-007` Definire platform concentration cap.
- [ ] `M36-008` Definire strategy concentration cap.
- [ ] `M36-009` Implementare multi-account ledger.
- [ ] `M36-010` Implementare multi-account OMS routing.
- [ ] `M36-011` Implementare account-specific rule resolution.
- [ ] `M36-012` Implementare account-specific kill switch.
- [ ] `M36-013` Implementare global kill switch.
- [ ] `M36-014` Implementare allocation tra account.
- [ ] `M36-015` Implementare copy-policy compliance.
- [ ] `M36-016` Verificare ToS multi-account.
- [ ] `M36-017` Eseguire paper multi-account.
- [ ] `M36-018` Eseguire shadow multi-account.
- [ ] `M36-019` Abilitare secondo account con size minima.
- [ ] `M36-020` Misurare cross-account slippage.
- [ ] `M36-021` Misurare global drawdown.
- [ ] `M36-022` Eseguire multi-account outage drill.
- [ ] `M36-023` Approvare o respingere ulteriore scaling.
- [ ] `M36-024` Aggiornare capacity model.
- [ ] `M36-025` Pubblicare il report di chiusura M36.

---

# Programma K — Chiusura del progetto e gestione continua

## M37 — Production certification

**Dipendenze:** M30-M36.
**Exit gate:** sistema certificato per uno specifico programma e versione.

- [ ] `M37-001` Congelare architecture diagram.
- [ ] `M37-002` Congelare data lineage diagram.
- [ ] `M37-003` Congelare execution sequence diagram.
- [ ] `M37-004` Congelare threat model.
- [ ] `M37-005` Congelare rule profile.
- [ ] `M37-006` Congelare broker capability matrix.
- [ ] `M37-007` Congelare model registry.
- [ ] `M37-008` Congelare prompt registry.
- [ ] `M37-009` Congelare strategy registry.
- [ ] `M37-010` Eseguire full regression suite.
- [ ] `M37-011` Eseguire full chaos suite.
- [ ] `M37-012` Eseguire full security suite.
- [ ] `M37-013` Eseguire full replay suite.
- [ ] `M37-014` Eseguire disaster recovery test.
- [ ] `M37-015` Eseguire audit reconstruction test.
- [ ] `M37-016` Eseguire kill-switch certification.
- [ ] `M37-017` Verificare zero bypass path.
- [ ] `M37-018` Verificare zero unresolved high findings.
- [ ] `M37-019` Verificare runbook coverage.
- [ ] `M37-020` Verificare operator access control.
- [ ] `M37-021` Firmare certification manifest.
- [ ] `M37-022` Pubblicare support mode finale.
- [ ] `M37-023` Pubblicare known limitations.
- [ ] `M37-024` Approvare production certification.
- [ ] `M37-025` Pubblicare il report di chiusura M37.

## M38 — Continuous operations

**Dipendenze:** M37.
**Exit gate:** processo continuo definito; il progetto non dipende da memoria
umana implicita.

- [ ] `M38-001` Definire daily operations checklist.
- [ ] `M38-002` Definire weekly performance review.
- [ ] `M38-003` Definire weekly risk review.
- [ ] `M38-004` Definire weekly reconciliation audit.
- [ ] `M38-005` Definire monthly alpha review.
- [ ] `M38-006` Definire monthly model review.
- [ ] `M38-007` Definire monthly dependency review.
- [ ] `M38-008` Definire monthly disaster-recovery check.
- [ ] `M38-009` Definire quarterly firm-rule review.
- [ ] `M38-010` Definire quarterly broker capability review.
- [ ] `M38-011` Definire quarterly security review.
- [ ] `M38-012` Definire quarterly prompt review.
- [ ] `M38-013` Definire model promotion process.
- [ ] `M38-014` Definire model rollback process.
- [ ] `M38-015` Definire strategy promotion process.
- [ ] `M38-016` Definire strategy retirement process.
- [ ] `M38-017` Definire plugin promotion process.
- [ ] `M38-018` Definire plugin revocation process.
- [ ] `M38-019` Definire rule-profile update process.
- [ ] `M38-020` Definire emergency change process.
- [ ] `M38-021` Definire post-incident learning process.
- [ ] `M38-022` Definire evidence retention policy.
- [ ] `M38-023` Definire cost and capacity review.
- [ ] `M38-024` Verificare prima operational cycle completa.
- [ ] `M38-025` Pubblicare il report di chiusura M38.

---

# Sequenza critica consigliata

La sequenza minima che porta al primo paper trading affidabile è:

```text
M00 → M01 → M02 → M03 → M04 → M05 → M06 → M07
    → M10 → M11 → M12 → M13 → M14 → M18
    → M19 → M20 → M21 → M22 → M23 → M24 → M25
    → M26 → M27 → M28 → M29 → M30 → M31 → M32
```

Eliza può procedere in parallelo dopo M06:

```text
M06 → M08 → M09 → integrazione in M11/M13/M17
```

Il percorso verso capitale reale è strettamente sequenziale:

```text
M32 Live Paper
  → M33 Shadow
  → M34 Evaluation
  → M35 Funded minimum-size
  → M36 Scaling
  → M37 Certification
```

---

# Stop conditions globali

Il progetto torna automaticamente a `PAUSED` quando:

- una suite hard-risk fallisce;
- esiste un mismatch broker/ledger non risolto;
- una regola firm necessaria è incerta o scaduta;
- il provider dati non garantisce provenance;
- compare una vulnerabilità high/critical nel percorso live;
- kill switch o flatten non sono verificabili;
- il paper/shadow model diverge oltre la tolerance approvata;
- l'edge non è positivo OOS netto dei costi;
- le condizioni operative violano i termini della firm;
- un modello o plugin non è riproducibile/versionato.

Il progetto è considerato completato soltanto quando M37 è chiusa per almeno un
programma prop-firm specifico. M38 rappresenta l'operatività continua successiva,
non una nuova feature phase.
