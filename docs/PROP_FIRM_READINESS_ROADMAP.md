# Oracle — Futures Prop-Firm Readiness Policy

> Versione: 2.0
> Verifica fonti selezionate: 2026-07-18
> Ambito: futures prop trading
> Natura: policy tecnica e operativa, non consulenza legale

Questa policy definisce quando Oracle può modellare, assistere o automatizzare
uno specifico programma. L'implementazione è governata dai gate G0-G9 in
[ROADMAP.md](../ROADMAP.md).

## 1. Principio

L'obiettivo non è “vincere ogni challenge”, ma:

> massimizzare con evidenza out-of-sample la probabilità e l'expected value di
> programmi esplicitamente supportati, senza violare termini, regole o limiti.

La compatibilità tecnica con una API non implica che:

- l'automazione sia consentita;
- un server remoto o VPS sia consentito;
- copy trading o account mirroring siano consentiti;
- evaluation e funded abbiano le stesse regole;
- una regola corrente si applichi ad account legacy.

## 2. Support mode

| Modalità | Significato | Autorità |
|---|---|---|
| AUTO_SUPPORTED | Automazione espressamente consentita, adapter e profilo certificati | OMS può inviare entro il profilo |
| ASSISTED_ONLY | Oracle analizza e controlla; submit/modify/cancel restano manuali | Nessun invio |
| RESEARCH_ONLY | Regole modellate e simulabili | Replay/backtest soltanto |
| UNSUPPORTED | Termini, fonti, piattaforma o adapter insufficienti | Fail closed |

Default per una nuova firm: **UNSUPPORTED**.

Una promozione richiede fonti ufficiali, review umana e data di efficacia. Una
modifica dei termini può causare demotion immediata.

## 3. Rule profile canonico

Chiave minima:

firm + program + stage + platform + account_size + account_vintage +
rule_version + effective_from

Campi obbligatori:

### Identità e governance

- support_mode;
- effective_from ed effective_to;
- source_url, source_checked_at, normalized_source_hash;
- reviewer e approver;
- account vintage e retrocompatibilità;
- piattaforma e adapter supportato.

### Autorità e infrastruttura

- automated strategy permessa;
- bot/algo/API permessi;
- submit/modify/cancel automatici permessi;
- copy trading e multi-account policy;
- VPS, VPN, remote server e device policy;
- credenziali e session restrictions.

### Economics e challenge

- account size e fee;
- profit target;
- minimum, winning e benchmark days;
- consistency e best-day rules;
- activation/reset fee;
- payout split, cap, schedule e buffer.

### Risk

- daily loss, base, timezone e reset;
- static/trailing drawdown;
- intraday o EOD;
- balance/equity e unrealized P&L;
- lock point;
- max contracts e mini-equivalenti;
- scaling;
- max position/exposure;
- breach action.

### Trading rules

- prodotti ammessi;
- sessioni e liquidation deadline;
- overnight/weekend;
- news blackout;
- price-limit e illiquid-market rules;
- HFT, latency, order-frequency e fill-exploitation restrictions.

Un campo necessario ma UNKNOWN rende il profilo RESEARCH_ONLY o UNSUPPORTED.

## 4. Rule decision contract

Ogni valutazione produce:

- ALLOW;
- DENY;
- PAUSE;
- FLATTEN;
- BREACH.

La decisione include reason code, profile version, account snapshot ID, market
snapshot ID, timestamp e input hash. Nessun booleano isolato è sufficiente per
audit o incident response.

## 5. Architettura richiesta

~~~mermaid
flowchart LR
    P[Strategy or PortfolioPlan] --> M[Mode and Account Guard]
    M --> R[Versioned Rule Resolver]
    R --> K[Hard Risk Kernel]
    K --> O[Durable OMS]
    O --> B[Certified Platform Adapter]
    B --> C[Prop Account]
    C --> X[Reconciliation and Ledger]
    X --> K
    K --> E[Audit Evidence]
~~~

Invarianti:

1. risk e rule resolver sono obbligatori;
2. equity usa unrealized P&L quando richiesto;
3. profilo sconosciuto o scaduto produce DENY;
4. kill switch cancella e chiude, poi verifica broker-side;
5. quantity usa ContractSpec e stop distance;
6. LLM non interpreta regole nella hot path;
7. ogni decisione è riproducibile.

## 6. Certificazione collegata ai capability gate

| Evidenza prop-firm | Gate Oracle |
|---|---|
| Fonti, termini, support mode e environment | G1 + G7 |
| ContractSpec, sessioni e market data | G2 |
| Account state, OMS e reconciliation | G3 |
| Drawdown, daily loss, caps, news e flatten | G4 |
| Backtest, costi, OOS, stress ed economics | G5 |
| Sandbox, paper, shadow, recovery e alert | G6 |
| Manifest di programma e smallest evaluation | G7 |
| Funded minimum-size e payout verification | G8 |

Una firm non viene “certificata in generale”. Si certifica una singola tupla
firm/program/stage/platform/account/vintage/rule-version.

## 7. Qualification policy economica

Sharpe, Profit Factor o pass-rate fissi non sono regole universali. La soglia di
lancio deve derivare da economics e risk budget del profilo.

Requisiti invarianti:

- expectancy OOS netta positiva;
- costi, slippage e fee inclusi;
- edge ancora positivo nello stress approvato;
- drawdown ordinario e stress con headroom rispetto alla firm;
- probabilità di breach e pass probability con intervallo di confidenza;
- lower confidence bound economicamente superiore al break-even;
- expected value netto positivo dopo fee, reset, activation e payout;
- numerosità sufficiente tramite power analysis o criterio documentato;
- nessuna concentrazione dominante per mese, strumento o regime;
- zero violazioni nei canonical replay;
- strategia preregistrata prima dell'holdout.

Default prudenti possono essere mantenuti in una QualificationPolicy versionata,
ma non vanno codificati come verità universali nella roadmap.

Il superamento autorizza paper/shadow. Non autorizza automaticamente evaluation
o funded.

## 8. Rollout

~~~mermaid
flowchart LR
    R[Research] --> H[Untouched Holdout]
    H --> P[Paper]
    P --> S[Shadow]
    S --> E[Smallest Evaluation]
    E --> F[Funded Limited]
    F --> X[Scale after verified payouts]
~~~

Regole:

- strategia modificata → ritorno a Research;
- rule profile modificato → ritorno almeno a canonical replay;
- adapter modificato → sandbox e shadow;
- finding high/critical → PAUSE;
- drift ledger/broker → PAUSE o FLATTEN;
- nessun scale-up durante drawdown o incident review;
- funded risk iniziale massimo 25% del budget consentito, salvo ADR e review.

## 9. Evidenza ufficiale verificata

Le pagine sono input volatili. Prima di acquisto, evaluation o funded serve un
nuovo check e un normalized source hash.

| Provider/program | Evidenza verificata | Modalità prudente |
|---|---|---|
| TopstepX API | La pagina ufficiale consente strategie automatizzate e tool terzi, ma vieta VPS, VPN e remote server: attività dal device personale | RESEARCH_ONLY candidate; AUTO solo con adapter e deployment locale conformi |
| Take Profit Trader PRO | La pagina ufficiale dichiara “No Trading bots/Algos” e richiede trade manuali | ASSISTED_ONLY |
| MyFundedFutures | La pagina ufficiale consente strategie automatizzate personalizzate ma vieta HFT, fill exploitation e copy trading tra trader | RESEARCH_ONLY candidate |
| FundedNext Futures Flex | Regole economiche EOD/consistency verificate; la pagina letta non certifica l'automazione | RESEARCH_ONLY |
| Apex | La fonte ufficiale indicata non era recuperabile automaticamente durante la review | UNSUPPORTED finché verificata manualmente |

Questa matrice non è una consulenza legale e non sostituisce contratto,
supporto ufficiale o termini dell'account.

## 10. Fonti selezionate

### Topstep

- https://help.topstep.com/en/articles/11187768-topstepx-api-access
- https://help.topstep.com/en/articles/8284197-trading-combine-parameters
- https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit
- https://help.topstep.com/en/articles/8284215-express-funded-account-parameters
- https://help.topstep.com/en/articles/8284223-what-is-the-scaling-plan
- https://help.topstep.com/en/articles/8284206-when-and-what-products-can-i-trade

API article last-modified dichiarato: 2026-06-23.

### Take Profit Trader

- https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171769361053-PRO-Account-Rules
- https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15170316538013-Rule-5-Be-Consistent
- https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15170265979165-Rule-3-Do-Not-Hit-End-Of-Day-EOD-Maximum-Trailing-Drawdown
- https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15170347090461-Rule-4-Trade-Approved-Products-During-Approved-Hours

PRO article updated-at dichiarato: 2026-06-24.

Una successiva probe HTTP automatizzata del 2026-07-18 ha restituito 403 sulle
pagine Zendesk: prima di certificare un account serve conservare snapshot,
hash e conferma manuale dei termini applicabili.

### MyFundedFutures

- https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices
- https://help.myfundedfutures.com/en/articles/8230009-news-trading-policy

Fair Play article last-modified dichiarato: 2025-11-24.

### FundedNext Futures

- https://helpfutures.fundednext.com/en/articles/14878751-what-is-fundednext-futures-flex-challenge
- https://helpfutures.fundednext.com/en/articles/14298225-what-is-the-maximum-loss-limit-at-fundednext-futures-and-how-does-it-work

Flex article last-modified dichiarato: 2026-07-05.

### Apex

- https://apextraderfunding.com/help-center/getting-started/prohibited-activities/
- https://apextraderfunding.com/help-center/getting-started/futures-trading-times/

Accesso automatizzato bloccato da Cloudflare durante la review; serve verifica
manuale e archiviazione dell'evidenza prima di qualsiasi classificazione.

## 11. Test obbligatori

| Livello | Prova |
|---|---|
| Unit | Contract math, timezone, drawdown, consistency e scaling |
| Property | Nessuna combinazione supera hard limits |
| Golden | Esempi ufficiali riprodotti esattamente |
| Replay | Equity intraday, session reset, news e liquidation |
| Broker contract | Paper, sandbox e adapter rispettano lo stesso contratto |
| Integration | Intent → rule/risk → OMS → broker → ledger |
| Chaos | Disconnect, stale data, duplicate/delayed fill, clock drift |
| Shadow | Decisioni e ordini simulati riconciliati allo stato reale |

## 12. Promotion e demotion

Promozione AUTO_SUPPORTED richiede approvazione esplicita dopo G7.

Demotion automatica ad ASSISTED_ONLY, RESEARCH_ONLY o UNSUPPORTED quando:

- fonte scaduta o regola cambiata;
- automazione/VPS/API non più consentiti;
- adapter o piattaforma cambiati;
- rule profile incompleto;
- breach non spiegato;
- mismatch ledger/broker;
- finding security high/critical;
- kill switch o flatten non verificabile.

## 13. Stop condition

La policy è soddisfatta per un programma quando:

- il profilo è versionato e fresco;
- automazione e vincoli infrastrutturali sono verificati;
- G2-G6 sono PASSED;
- la smallest evaluation è completata senza policy breach;
- manifest e support mode sono approvati.

Le firm che vietano automazione possono essere complete soltanto come
ASSISTED_ONLY.
