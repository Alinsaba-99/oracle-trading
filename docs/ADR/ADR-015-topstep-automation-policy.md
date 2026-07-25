# ADR-015: Topstep Automation / VPS / Device Policy

> Status: ACCEPTED
> Date: 2026-07-25
> Supersedes: nothing
> Related: BL-071 (BACKLOG.md), PROP_FIRM_READINESS_ROADMAP.md §9

## Context

Il programma Topstep TC 50K è il candidato fallback per G7 (vedi
[BL-100](../../BACKLOG.md)). Le fonti ufficiali Topstep vietano
esplicitamente "trading bots / algos / API automation"? **No**, non
in maniera uniforme:

- **TopstepX** (la nuova piattaforma) **consente** strategie automatizzate
  e tool terzi (help.topstep.com/en/articles/11187768); **vieta** VPS,
  VPN, remote server. L'attività deve avvenire dal device personale
  del trader.

Questo pone un vincolo operativo reale: Oracle può eseguire Topstep TC
50K in modalità `AUTO_SUPPORTED` **ma solo se**:

- il deployment è locale (no VPS, no Docker remoto);
- il dispositivo che esegue è il "personal device" del trader;
- il rischio è sufficiente basso da non richiedere 24/7 operation;
- l'account vintage è registrato coerentemente.

## Decision drivers

- L'automazione è consentita ma con vincoli residenziali
- L'infrastruttura Oracle (Compose con NATS, Redis) è server-side
  e potrebbe essere VPS-equivalente
- Serve una posizione esplicita per i deployment che aspirano a G7

## Decision

Oracle accetta Topstep come `RESEARCH_ONLY` e come `AUTO_SUPPORTED`
solo quando **tutte** le seguenti condizioni sono verificate:

1. **Local-only deployment**: il binario Oracle gira su un personal
   device del trader (laptop, desktop). Non su VPS/cloud. Comando
   `make docker-up` NON usato in produzione.
2. **Single-tenant**: un solo account Topstep per istanza di Oracle,
   con credenziali dedicate. Niente multi-account.
3. **Nessun bot esterno**: tutte le operazioni passano per OMS
   durevole locale. Niente bridge verso VPS per fill.
4. **Risk conformant**: il risk kernel è fail-closed (vedi G4) e il
   profile versionato Topstep TC 50K è caricato.

Fino a quando queste condizioni **non** sono verificate, Oracle
classifica Topstep come `RESEARCH_ONLY` per default.

## Alternatives considered

### A. ASSISTED_ONLY
Oracle genera segnali ma l'utente deve cliccare manualmente su TopstepX.
Più sicuro ma non sfrutta OMS durevole e reconciliation, perdendo il
valore aggiunto della piattaforma.

### B. AUTO_SUPPORTED senza restrizioni
Il path è più breve ma viola i ToS TopstepX e mette l'account a
rischio di breach/chiusura.

### C. Scelta di un'altra firm (MyFundedFutures)
Consente automation ma gli account sono più piccoli e il payout
è meno prevedibile. Trattato in BL-100.

## Consequences

### Positive

- Posizione esplicita per chi vuole G7 su Topstep
- Riduce il rischio di breachToS non intenzionale
- Allinea con PROP_FIRM_READINESS_ROADMAP §9

### Negative

- Limitazione operativa per chi vuole 24/7
- Richiede che il deployment sia locale (no Docker)

### Enforcement

- ADR incluso in `docs/ADR/README.md`
- `mode=funded` in `core/domain/guard.py` richiede conferma esplicita
  dell'utente prima di inviare ordini a Topstep
- TODO: aggiungere check nel CLI `--mode=funded` per conferma

## References

- https://help.topstep.com/en/articles/11187768-topstepx-api-access
- [PROP_FIRM_READINESS_ROADMAP.md §9](../PROP_FIRM_READINESS_ROADMAP.md)
- [BACKLOG.md BL-071](../../BACKLOG.md)
- [BACKLOG.md BL-100](../../BACKLOG.md)