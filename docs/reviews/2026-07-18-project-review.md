# Oracle Trading — Complete Project Review

> Data: 2026-07-18
> Scope: repository corrente, working tree inclusa
> Verdict: **REQUEST CHANGES / NOT LIVE-READY**
> Architectural status: **BLOCK**

## 1. Scope e metodo

Sono stati ispezionati:

- PROJECT.md e documentazione canonica;
- roadmap Phase e backlog atomico precedente;
- ADR e specifica architetturale;
- pyproject, uv.lock, package lock Node, CI e Docker;
- agent, analytics, backtest, genetics, policy, execution, API e dashboard;
- test e static analysis;
- fonti ufficiali selezionate delle prop firm.

Verifiche fresche:

- 1.605 test Python passati, 2 skipped;
- Ruff pass;
- 397 file formattati;
- mypy su 261 source file pass, con override espliciti;
- uv lock e clean sync pass;
- pip-audit sull'ambiente installato: nessuna vulnerabilità nota; il tool non
  ha riconosciuto direttamente `uv.lock`, quindi il gate lockfile/SBOM resta aperto;
- dashboard 15 test e build pass;
- Eliza 2 test, typecheck e build pass;
- audit dependency Node.

Sono state avviate lane indipendenti code-review, architecture e dependency. Il
runtime subagent ha terminato le lane con errore provider 402; una lane ha
fornito findings preliminari sullo stack, verificati localmente. Per questo non
viene emesso un verdetto APPROVE indipendente.

## 2. Sintesi

Il progetto ha una base ampia e testata, ma confonde ancora tre categorie:

1. **implemented** — codice e test locali esistono;
2. **qualified** — comportamento realistico e riproducibile è provato;
3. **authorized** — il percorso può operare su un account reale.

Molti componenti sono implemented, pochi sono qualified e nessuno è authorized
per live/funded. Il rischio principale non è la quantità di codice, ma la
presenza di fallback, state in-memory e composition root che possono evitare i
confini dichiarati.

## 3. Finding critici

### C1 — Execution non ancora non-bypassabile

**Evidenza:**

- execution/order_manager/manager.py:26-52 accetta risk_manager assente;
- apps/cli/trade_commands.py:42-50 costruisce OrderManager senza risk;
- agents/orchestrator/graph.py:253-267 crea assessment permissivo quando risk
  manca;
- agents/orchestrator/graph.py:359-381 può saltare il nodo risk;
- execution/order_manager/bridge.py:24-28 e 88-99 rende il risk opzionale;
- execution/order_manager/bridge.py:45-66 usa prezzo fallback 100.

**Impatto:** un adapter o una composition root non certificata può produrre un
ordine senza profilo, contract spec o hard risk.

**Intervento eseguito:** il submit pubblico CLI verso broker non-paper è ora
fail-closed e ha regression test.

**Residuo:** OrderManager e tutte le composition root devono richiedere un
ExecutionContext certificato. Non dichiarare zero-bypass finché G4 non passa.

### C2 — Nessun account source of truth durevole

**Evidenza:**

- OrderManager conserva ordini, fill e idempotency in dizionari in-memory;
- PaperBroker conserva ordini/fill/position in-memory e usa prezzo sintetico;
- la CLI ricrea broker e manager per comando;
- gli SQLite esistenti sono inbox/journal separati, non ledger riconciliato.

**Impatto:** restart, retry, duplicate fill e comandi separati possono perdere o
divergere stato economico.

**Decisione:** PostgreSQL ledger/OMS production, SQLite dev/test, outbox e
reconciliation. Vedi ADR-009 e G3.

### C3 — API e deployment possono partire fail-open

**Evidenza:**

- apps/api/config.py:11-15 usa api_key vuota, host 0.0.0.0 e debug true;
- apps/api/main.py:37-44 emette solo warning senza key;
- Docker avvia Uvicorn su 0.0.0.0;
- Compose pubblica porte dati e contiene password development;
- Compose non includeva un servizio applicativo completo.

**Impatto:** una futura attivazione del container può esporre API senza
autenticazione e infrastruttura dati non isolata.

**Decisione:** startup production deve fallire senza auth/secrets; deployment
privato, non-root e locked. È blocker G1/G6.

### C4 — Live/funded claim non supportabile

ContractSpec futures, calendari, roll, ledger, OMS, reconciliation, kill switch,
paper qualification e adapter certificato non sono completi. Nessuna firm può
essere AUTO_SUPPORTED oggi.

## 4. Finding high

### H1 — Backtest non qualificato

- analytics/backtest/engines/nautilus.py usa Equity, cash account e fallback;
- eccezioni sono ignorate in close/extract/account;
- l'equity curve viene ricostruita fuori dal motore;
- walk-forward tratta metriche OOS come best-effort;
- FeatureStore ignora file Parquet illeggibili;
- vectorbt e Nautilus non hanno parity certificata;
- PyBroker è un terzo percorso non installato dall'extra omonimo.

**Decisione:** discovery vectorized, un solo motore event-driven di
qualification, PyBroker deprecato. Vedi ADR-011.

### H2 — Dependency direction incoerente

Import graph osservato:

- execution → agents;
- policy → execution;
- analytics ↔ market;
- analytics → execution;
- agents → genetics → analytics.

**Impatto:** safety control plane dipende da research/intelligence.

**Decisione:** modular monolith con layer inward e ports/adapters. Vedi ADR-008.

### H3 — ADR storici non corrispondevano alla realtà

- ADR-001 imponeva NATS universale;
- ADR-002 dichiarava QuestDB primario;
- ADR-004 plugin-first universale;
- ADR-005 struttura services/libraries non presente.

**Intervento:** ADR-008/009 li supersede; creati indice e lifecycle.

### H4 — Docker non riproducibile

Il Dockerfile:

- non usava uv.lock;
- installava editable dev dependency;
- copiava solo parte dei package;
- operava come root;
- non aveva .dockerignore;
- non separava build/runtime;
- non garantiva auth production.

**Decisione:** non considerare Compose production. Work package G0/G6.

### H5 — Python dependency model duplicato

pyproject contiene project extras dev/pybroker e dependency-groups con versioni
diverse. L'extra pybroker non installa lib-pybroker. La CI precedente usava pip
e ignorava uv.lock.

**Intervento:** CI e Makefile ora usano uv lock. La normalizzazione degli extra
resta P1.

### H6 — vectorbt portability e licensing

uv.lock risolve vectorbt 1.1.0 sulle piattaforme correnti ma 0.23.3 su macOS
x86, insieme a dipendenze incompatibili con Python 3.12. La licenza upstream è
Apache 2.0 con Commons Clause. Nautilus Trader dichiara LGPL-3.0-or-later: non
ne impedisce la valutazione, ma obblighi di distribuzione/linking vanno inclusi
nell'inventario licenze prima di distribuire immagini o appliance.

**Decisione:** RESEARCH_ONLY, support matrix esplicita e legal review prima di
uso commerciale o distribuzione.

### H7 — Configuration model non rappresenta le modalità operative

OracleSettings ammette development/staging/production, mentre i contratti usano
replay/paper/shadow/live e la roadmap richiede evaluation/funded. Il loader
gestisce gli override nested in modo non chiaramente coerente con
pydantic-settings.

**Decisione:** separare environment tecnico e trading authority; aggiungere
startup crossing tests in G1.

## 5. Finding medium

### M1 — Claim mypy “strict” sovrastimato

La configurazione ignora interi moduli genetics e PyBroker. Il comando passa,
ma il documento deve dichiarare gli override e ridurli nel tempo.

### M2 — Warning budget assente

La suite produce 319 warning, inclusi Starlette/httpx, LightGBM feature name e
warning numerici/genetici. Un baseline verde senza budget può degradare
silenziosamente.

### M3 — Coverage non rappresentativa

tool.coverage.run indica source oracle, package inesistente; la CI misura solo
core. Il totale dei test non equivale a coverage del percorso risk/execution.

### M4 — Dashboard bundle pesante

La build genera un chunk Plotly circa 4,5 MB. Non blocca G0, ma richiede lazy
loading o chart strategy prima di operazioni remote/low-bandwidth.

### M5 — Metrics endpoint non reale

apps/api/main.py espone contatori statici. Non è osservabilità production.

### M6 — Infrastruttura dichiarata oltre l'uso

Redis, PostgreSQL, QuestDB, Qdrant, Loki e Prometheus sono scaffolding. Devono
essere marcati DEFERRED/EXPERIMENTAL finché non sono integrati e testati.

### M7 — Documentazione storica contaminata

PROJECT conteneva sezioni duplicate, stack discordanti e Phase complete.
phase6-plan conteneva anche testo spurio generato. I piani storici non avevano
banner di deprecazione.

**Intervento:** documentazione consolidata, testo spurio rimosso, archive
policy aggiunta.

### M8 — Eliza ha debito transitive-dependency non bloccante

`npm audit` riporta 5 finding low nella catena `@elizaos/core` →
`crypto-browserify` → `elliptic`; l'installazione segnala inoltre
`@ungap/structured-clone@1.2.0` come deprecato. Il fix automatico proposto è
breaking e non va applicato alla cieca. Eliza resta read-only; l'upgrade deve
passare contract test del plugin e una nuova dependency review.

## 6. Finding prop-firm

### TopstepX

La pagina ufficiale verificata consente strategie automatizzate e tool terzi,
ma vieta VPS, VPN e remote server. Un deployment cloud di Oracle non è quindi
automaticamente compatibile.

### Take Profit Trader PRO

La pagina ufficiale verificata vieta bot/algo e richiede esecuzione manuale.
Modalità massima prudente: ASSISTED_ONLY. Una successiva probe automatizzata ha
ricevuto 403, quindi snapshot e hash devono essere archiviati prima di G7.

### MyFundedFutures

La pagina ufficiale consente automazione personalizzata ma vieta HFT,
fill-exploitation e copy trading tra trader. Serve adapter/rule certification.

### FundedNext Futures Flex

Economics e consistency sono verificabili, ma la fonte letta non autorizza da
sola l'automazione. RESEARCH_ONLY finché i termini execution non sono verificati.

### Apex

La pagina ufficiale era protetta da Cloudflare e non è stata verificata
automaticamente. Default: UNSUPPORTED.

## 7. Dilemmi risolti

| Dilemma | Decisione |
|---|---|
| Microservizi o monolite | Modular monolith iniziale; estrazione solo con ADR e SLO |
| NATS ovunque | No; sync safety path, outbox/eventi alle boundary |
| QuestDB subito | No; deferred fino a benchmark |
| PostgreSQL o SQLite | PostgreSQL production authority; SQLite dev/test |
| Redis come stato | No; cache ricostruibile |
| Più motori backtest | Discovery vectorized + un solo qualification engine |
| PyBroker | Deprecated |
| LLM nella execution | Vietato |
| ElizaOS | Intelligence mesh read-only |
| Phase roadmap | Deprecated; capability gate G0-G9 |
| Metriche fisse per challenge | Policy economica versionata, soglie derivate da EV/risk |
| Prima firm | Nessuna scelta marketing; selezione dopo terms/API/device verification |
| Submit CLI non-paper | Disabilitato fino a certificazione; gli altri bypass restano nel gate G1/G4 |

## 8. Modifiche effettuate

### Codice e stack

- apps/dashboard/package.json e lock: Vite 8/plugin React upgrade;
- Node 24 standardizzato;
- CI Node audit completo;
- CI Python locked con uv;
- Makefile e environment check allineati al workflow uv frozen;
- Ruff config allineata;
- stato locale OMX/lean-ctx e TypeScript build-info esclusi dal repository;
- CLI broker non-paper fail-closed;
- regression test del blocco live.

### Documentazione

- PROJECT riscritto sullo stato verificato;
- Master Roadmap v2 a capability gate;
- Status con evidenza fresca;
- Prop-firm policy v2;
- living ARCHITECTURE;
- ADR 008-013;
- ADR index e template;
- piani Phase deprecati e indicizzati;
- backlog atomico v1 archiviato;
- SPECIFICATION e CONTRIBUTING riallineati.

## 9. Rischi residui e ordine di intervento

1. consolidare la working tree;
2. CI remota pulita e supply-chain gate;
3. API production fail-closed;
4. risk obbligatorio e zero-bypass test;
5. ContractSpec e calendari;
6. ledger/OMS/outbox/reconciliation;
7. motore qualification;
8. paper/shadow operations;
9. selezione e certificazione programma;
10. smallest evaluation.

## 10. Verdict

**REQUEST CHANGES.**

Il progetto è una piattaforma di ricerca solida e ampia, ma non è merge-ready
come “autopilot live” e non è prop-firm ready. La documentazione e alcuni gate
tecnici sono stati corretti; i blocker G1-G6 restano implementazione necessaria.
