# Edge Research Factory — design spec

> Data: 2026-08-21 · Stato: PROPOSED (attende review utente)
> Branch: `feat/p1-metrics-truth` · Sostituisce operativamente il motore
> "Mutageno G10-G14" come generatore di piste edge; ne riusa l'ambizione
> ma ancora ogni ipotesi a fonti concrete invece di generare strategie al buio.
> Gerarchia: questa spec → BACKLOG (BL-700..) → ROADMAP §14 → ADR (quando servono).

## 0. Obiettivo

Un sistema ripetibile che trasforma **tutto ciò che sappiamo già** (knowledge
base 13 domini + corpus MoonDev/trading-os) in **ipotesi edge pre-registrate,
amplificate con letteratura 2022-2026 e web, adattate ai dati che possiedi
davvero, e qualificate con il gauntlet ADR-017 già in casa**.

Doppio canale per ogni edge approvato:

| Canale | Variante | Gate |
|---|---|---|
| **Personal book** | alta-vol | Sharpe/Sortino/Calmar + haircut Sharpe (BL-KB-99) sopra soglie pre-registrate; DD dichiarato, mai nascosto |
| **Funded eval** (Topstep/MFFU) | σ-scaled dentro i vincoli G4 | passa i criteri G6 nella catena paper canonica (BL-615) **prima** di pagare qualsiasi eval |

Target dichiarato dall'utente: 6-15%/mese personal + eval superate.
**Dichiarazione onesta**: S0.2 ha misurato che il soffitto dei segnali
attuali è +2-6% lordo/anno. La factory esiste per alzare quel soffitto
cercando edge *nuovi* (non trend ES daily, che è morto); se non ci riesce,
lo deve dire con evidenza, non con marketing.

## 1. Principi non negoziabili

1. **Pre-registrazione prima del test**: ogni ipotesi qualificabile ha una
   spec YAML versionata + hash prima di toccare i dati di test
   (infrastruttura BL-615: `PaperRunSpec`, manifest con sha256).
2. **Nessun risultato silenzioso**: ogni REJECTED è un report committato in
   `docs/reports/edge-factory/` con evidenza; il registry tiene lo stato.
3. **Web untrusted**: la letteratura esterna entra come evidenza citata
   (fonte, data, URL, sha256 dello snapshot quando possibile), mai come
   verità. Claim di rendimento esterni (MoonDev inclusi) non entrano mai
   nel registry senza il flag `claim_non_verificato`.
4. **$0/mese** (ADR-020): nessun dato a pagamento. Binance Vision, lake
   esistente, IBKR paper going-forward, fonti free verificate 2026-08-16.
5. **Decay prima della fiducia**: ogni ipotesi porta il suo haircut
   post-pubblicazione atteso (McLean-Pontiff, KB-03) come campo del
   registry, applicato ai criteri di promozione.

## 2. Architettura: 5 stadi

```
STAGE 1 CORPUS MINING          STAGE 2 AMPLIFICAZIONE        STAGE 3 ADAPTER
┌────────────────────────┐     ┌────────────────────────┐    ┌─────────────────────────┐
│ KB 13 domini (112 BL-KB)│ ──► │ paper 2022-2026 (SSRN/ │ ─► │ matrice (fattore × asset│
│ moondev-repos (D1-D15)  │     │ arXiv/NBER) + web 5 MCP│    │ × timeframe) prioritiz- │
│ video-library 835 trans │     │ + OSS repo + confutaz. │    │ zata per data-readiness │
└───────────┬────────────┘     └───────────┬────────────┘    └───────────┬─────────────┘
            ▼                              ▼                              ▼
        HYPOTHESIS REGISTRY (YAML, versionato in git, append-only)
            ▼
STAGE 4 QUALIFICAZIONE                                        STAGE 5 DUAL CHANNEL
┌────────────────────────────────────────────────────┐       ┌──────────────────────┐
│ IC screen (Spearman + block bootstrap) / walk-fwd  │ ───►  │ personal: high-vol   │
│ Gauntlet ADR-017: DSR/PBO/CPCV, bear-2022 separato │       │ funded: σ-scaled G4  │
│ runner canonico `oracle paper run --spec`          │       │ eval pagata solo dopo│
└────────────────────────────────────────────────────┘       └──────────────────────┘
```

Codice target: `analytics/research/factory/` (registry.py, amplify.py,
adapter.py, ic_screen.py) + `scripts/run_edge_factory.py` orchestratore.
Il registry vive in `docs/knowledge-base/edge-factory/registry/<dominio>.yaml`
(committato, append-only: stati cambiano, ipotesi non si cancellano).

## 3. Stage 1 — Corpus mining

Tre miner indipendenti, output = entries nel registry.

### 3.1 KB miner (13 domini, 112 BL-KB items)
Per ogni dominio: estrai ogni ipotesi testabile come record con campi:
`meccanismo`, `perché_esiste` (ragione economica), `effect_size_dichiarata`,
`decay_atteso`, `dati_richiesti`, `asset_candidati`, `timeframe`,
`stato=da_amplificare`. L'audit 2026-08-17 è input privilegiato: i suoi
gap (BL-KB-99..115) sono ipotesi già triaged. Priorità dichiarate:
**BL-KB-102 VPIN** (proxy order flow L1 free — sblocca un dominio
hard-blocked), BL-KB-103 Value&Momentum Everywhere, BL-KB-99 Haircut
Sharpe (prereq di validazione, va in Stage 4 come strumento, non ipotesi).

### 3.2 MoonDev miner (trading-os/knowledge)
Da `RISPOSTE_D1-D15.md`, `NOTES.md`, `INDEX.md`: i fattori già triaged
(funding extremum, liquidation cascade reversal, BB squeeze release,
CVD divergence, session seasonality) con meccanismo + dati $0 (Binance
Vision). Flag `origine=practitioner` → haircut conservativo di default.

### 3.3 Transcript miner (trading-os/video-library, 835 file)
Mai minato sistematicamente. Scan dei transcript per idee fattore/
strategia con timestamp + riferimento video. Output a bassa confidenza:
`origine=video`, `confidence=bassa`; passa in Stage 2 solo se trova
riscontro in letteratura. Costo: zero (testi locali).

### Schema registry (per dominio)

```yaml
schema_version: 1
domain: crypto-microstructure
hypotheses:
  - id: EF-001
    nome: funding-extremum-reversal
    meccanismo: funding rate estremo → posizione affollata → reversal
    perche_esiste: costo del carry spinge i marginal trader fuori
    origine: practitioner  # kb | practitioner | video | letteratura
    fonti: [trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md#funding]
    effect_size_dichiarata: non_quantificata
    decay_atteso_pct: 30            # haircut McLean-Pontiff style
    dati_richiesti: [fundingRate 1h, OHLCV 1h]
    dati_posseduti: true            # verificato da Stage 3
    asset_candidati: [BTCUSDT, ETHUSDT, SOLUSDT]
    timeframe: [1h, 4h]
    stato: da_amplificare           # da_amplificare|amplificata|in_qualifica|APPROVED|REJECTED|morta
    evidenza: []                    # append-only: test, report, citazioni
```

## 4. Stage 2 — Amplificazione (la parte "folle")

Per ogni ipotesi `da_amplificare`, una batteria con i 5 search MCP
(Tavily, Brave, Exa, SearXNG, DuckDuckGo — tutti $0, già connessi):

1. **Conferma accademica**: SSRN/arXiv/NBER + journal; cerca il paper
   originale E le repliche. Campo `effetto_replicato: si|no|dibattuto`.
2. **Confutazione attiva**: ricerca dedicata a "X anomaly disappears /
   does not replicate / transaction costs" — se la letteratura ha già
   ucciso l'edge, lo segniamo `morta` subito (risparmio di mesi).
3. **Gap hunting**: per i 13 domini, query mirate ai buchi dichiarati
   dall'audit (paper 2022-2026, LLM sentiment, deep RL portfolios,
   on-chain moderno) per **nuove** ipotesi non presenti in KB.
4. **OSS ispezionabile**: implementazioni GitHub del fattore — si legge
   il codice, non ci si fida del README.
5. Ogni evidenza: citazione con URL + data fetch + snapshot sha256 dove
   possibile (pattern `docs/firm_sources/`).

Output: ipotesi promossa ad `amplificata` (con letteratura a supporto),
`morta` (confutata), o `già_nota_saturo` (troppi crowding → decay alto).

## 5. Stage 3 — Asset Context Adapter

La mappa dei dati posseduti (verificata, ADR-020 + BL-301/307):

| Asset/serie | Profondità | Fattori abilitati |
|---|---|---|
| BTC/ETH/SOL/BNB 1m | 2017→, milioni di barre | microstruttura crypto, funding, liq, seasonality oraria |
| Binance Vision fundingRate/liq snapshot | storico free | fattori esclusivi del canale crypto |
| EURUSD + 58 FX 1m | 2003→ (Dukascopy) | FX intraday, carry, sessioni |
| ES/NQ/GC/CL 1m | going-forward dal 2026-07 (IBKR cron) | solo accumulo: non qualificabile su storia |
| ES 1h / futures 1d lake | 10+ anni | regime, trend, roll |
| SimFin 185 ticker fundamental | 2015→ | Lane B, fattori value/momentum |
| FRED macro PIT | vintage ALFRED | macro factors con as_of |

Per ogni ipotesi `amplificata`: (a) verifica `dati_posseduti`;
(b) riscrittura contesto-specifica (seasonality → oraria su crypto 24/7,
macro → beta-adattato all'asset, order-flow → VPIN su L1 dove L2 è
paywalled); (c) riga nella **matrice di test** `(fattore × asset ×
timeframe)` con priorità = data-readiness × EV atteso × (1 − decay).

Ipotesi senza dati posseduti: `stato=morta_per_dati`, con nota di cosa
sbloccherebbe (es. BL-097/098 API key = sblocco futures intraday storici).

## 6. Stage 4 — Qualificazione pre-registrata

Catena unica, zero eccezioni, riusa tutto ciò che esiste:

1. **Pre-registrazione**: spec YAML + hash (PaperRunSpec / registry entry
   congelato) PRIMA del test. Violazione = test nullo.
2. **IC screen** per i fattori: Spearman IC su orizzonti non sovrapposti,
   block bootstrap, criterio pre-registrato `ICIR > 0.05, t-block > 2.5`
   (dallo studio 2026-08-19 §5), haircut 30% post-pubblicazione.
   Implementazione: `analytics/research/factory/ic_screen.py`
   (BL-KB-102/VPIN alimenta la famiglia order-flow su L1).
3. **Walk-forward / anti-beta**: benchmark corretto dal giorno 1
   (lezione BL-093: mai misurare beta come alpha).
4. **Gauntlet ADR-017**: DSR ≥ 0.95, PBO < 0.1, CPCV OOS Sharpe ≥ 0.5,
   bear-2022 separato; poi catena paper canonica per ciò che è
   trade-producing (`oracle paper run --spec`, BL-615).
5. Verdetto nel registry: `APPROVED` (report in
   `docs/reports/edge-factory/`) o `REJECTED` (report uguale, il silenzio
   è vietato).

## 7. Stage 5 — Doppio canale

- **Personal book**: variante alta-vol. Promozione solo con haircut
  Sharpe sopra soglia pre-registrata per classe; DD misurato riportato
  nel registry; sizing target-vol.
- **Funded eval**: variante σ-scaled dentro i vincoli G4 (adapter
  PropFirm già cablato, BL-070). Regola dura: **nessuna eval si paga**
  finché la variante non passa i criteri G6 (pass ≥ 0.90, DD ≤ 3%) su
  ≥100 sessioni nella catena paper canonica. Economia: S0.2 dice che
  l'eval è un'opzione sul passare — va comprata solo ITM.

## 8. Kill criteria e cadenza (anti-autoinganno)

- Sprint di **4 settimane**, go/no-go scritto in
  `docs/reports/edge-factory/sprint-N.md` alla fine di ciascuno.
- Sprint 1 (mining+amplificazione) deve produrre **≥ 15 ipotesi
  amplificate**; se ne produce < 8 → il corpus non basta, si espande
  lo Stage 2 prima di qualificare.
- Dopo Stage 4 del primo sprint: se **< 2 fattori superano l'IC screen**
  → stop, report onesto, rivalutazione del canale (non si continua a
  costruire moduli attorno a zero edge).
- Nessun modulo nuovo (catalogo 100 strategie, evolution loop) prima di
  ≥ 1 edge APPROVED. Mutageno G10-G14 resta congelato.

## 9. Backlog proposto (serie BL-700)

| BL | Cosa | Dipendenza |
|---|---|---|
| BL-700 | Schema registry + `analytics/research/factory/registry.py` + test | — |
| BL-701 | KB miner (13 domini → registry) | BL-700 |
| BL-702 | MoonDev miner (trading-os/knowledge → registry) | BL-700 |
| BL-703 | Transcript miner (835 transcript → registry) | BL-700 |
| BL-704 | Amplificatore: batteria search MCP + evidenza citata | BL-701..703 |
| BL-705 | Asset adapter: verifica dati + matrice di test | BL-704 |
| BL-706 | IC screen (`ic_screen.py`: Spearman + block bootstrap) + golden test | BL-700 |
| BL-707 | Haircut Sharpe (BL-KB-99) come strumento del gauntlet | — |
| BL-708 | Qualificazione primo lotto + report sprint 1 | BL-705/706/707 |
| BL-709 | Dual-channel promotion policy (spec personal vs funded) + ADR | BL-708 |

Nota: BL-097/098 (API key Databento + gateway IBKR manuale) restano i
due sblocchi umani che alzerebbero il soffitto dati; la factory parte
senza aspettarli.

## 10. Rischi dichiarati

1. **Amplificazione senza fine**: il web è infinito; il budget per stage
   è a sprint, non a curiosità. Ogni ipotesi che entra in Stage 2 ha un
   costo tempo stimato nel registry.
2. **Practitioner bias**: i fattori MoonDev arrivano da un incentivo a
   vendere (studio 2026-08-19 §1.4) → haircut conservativo + confutazione
   obbligatoria prima della qualificazione.
3. **Crowding**: ipotesi "famose" sono probabilmente già arbitrate; il
   campo `decay_atteso_pct` e lo screening di crowded strategies
   (BL-KB-109) sono il filtro.
4. **Il target 6-15%/mese**: resta dichiarato come obiettivo dell'utente,
   non come previsione del sistema. Ogni report della factory riporta
   l'atteso onesto accanto al target.

## 11. Cosa questa spec NON è

- Non è un rebuild: riusa catena paper (BL-615), gauntlet ADR-017,
  lake, G4, knowledge base.
- Non è "diventare MoonDev": nessun live, nessun claim di ROI.
- Non tocca l'edge esistente: Lane B resta bloccata finché non passa
  la variante unica pre-registrata (decisione pendente separata,
  compatibile con BL-708).
