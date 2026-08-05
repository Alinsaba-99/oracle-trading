# S0.1 — Autopsia BL-023: perché la strategia è morta

> Deliverable del piano production-grade (commit `3bdef58`), sezione S0.1:
> "decomporre il fallimento PRIMA di ampliare la ricerca (dati vs
> implementazione vs costi vs benchmark vs orizzonte vs regime)".
>
> Data: 2026-08-05. Ogni numero in questo documento è tracciato a un report
> sorgente versionato nel repo (vedi §Fonti). Nessuna conclusione è basata
> su memoria o su run non ripetibili.

## 0. Il paziente: cosa stiamo dichiarando morto

La lane di ricerca BL-023/M31 ha prodotto, in ordine cronologico:

1. **M31 closeout 2026-07-19**: APPROVED (median Sharpe 1.013, 48 oss.,
   luck p 0.008) — poi invalidato da ADR-014 (evidence loss).
2. **Re-run canonico 2026-07-30** (`ce644ba`, report
   `m31-historical-replay-qualification.md` rigenerato): **REJECTED** —
   median Sharpe -1.15, median return -0.24%, worst DD 12.7% > 4%,
   48 hard breach. Prima smentita ufficiale del closeout.
3. **Fase 5 (re-run onesto, 2026-08-04)**: REJECTED — Sharpe -0.251,
   return -1.22%, luck p 1.0, 6 regimi × 8 varianti ma N reale = 6.
4. **Fase 5b (N onesto ADR-016 §6)**: REJECTED — 17 curve uniche,
   Sharpe -0.31, worst DD 5.63% > 4%.
5. **Fase 5c (8 candidati segnale nel gate reale)**: 8/8 REJECTED.
   Migliore: donchian_breakout Sharpe +0.216, ma 16 hard breach e DD 4.77%.
6. **Fase 2 (walk-forward multi-asset)**: 0/9 asset×segnale battono il
   buy&hold su ES/SPY/BTCUSDT out-of-sample (test ≥ 2023).

**Verdetto cumulativo: nessun edge sfruttabile in questo spazio.**
L'autopsia serve a capire *perché*, per non ripetere l'errore in S1.

## 1. Decomposizione sui sei assi del piano

### Asse 1 — Dati: NON COLPEVOLE

- Lake live con pin verificati (ES 6523 righe, SPY 6679, BTCUSDT 3275),
  hash in header di ogni report, PIT verificato, no-lookahead
  (`shift(1)` nel walk-forward).
- Il fallimento persiste anche con dati puliti e split onesto
  (train < 2023 / test ≥ 2023): la Fase 2 usa gli stessi dati e conferma
  il verdetto, quindi i dati non sono la causa.
- Limitazione residua dichiarata: ES continuous Yahoo come proxy di prezzo
  MES (roll/adjustment del provider). Non è la causa del fallimento ma
  resta un caveat per S1.3.

### Asse 2 — Implementazione: ASSOLTA con due difetti trovati

L'implementazione è *migliorata a ogni fase* (fix Lorentzian causal,
regime ribilanciato, risk adapter cablato, fail-soft su `rsi()`/`ema()`/
`atr()`, N onesto) e il verdetto REJECTED ha *retto a ogni fix*: questo è
il punto di forza dell'autopsia — la morte non è un artefatto di un bug.

Due difetti reali però emergono, e vanno registrati come lezioni per S1:

- **Difetto A — candidati duplicati.** `bollinger_reversion` e
  `zscore_reversion` sono la stessa regola matematica:
  `close < media − 2·devstd` ≡ `z-score < −2` (stessi parametri 20/2.0,
  exit identico sopra la media; `BbandReversion` e `ZscoreReversion` in
  `analytics/strategy/signals.py:82,202`; l'unica differenza è la
  convenzione ddof della deviazione: polars `ddof=0` in `bbands()` vs
  pandas default in `ZscoreReversion`). Verificato empiricamente: su 136
  osservazioni, 88 byte-identiche e le restanti 48 differiscono solo per
  quel decimale. **8 candidati = 7 ipotesi indipendenti.** La multiplicity
  dichiarata era sovrastimata di 1.
- **Difetto B — matrice varianti teatrale.** Le 8 varianti "intelligence"
  (scouts on/off × debate on/off × fund-manager baseline/challenger)
  producono metriche **byte-identiche per tutti i 17 periodi** di ogni
  candidato (verificato sul JSON: 17/17 periodi con 8/8 curve identiche).
  N=136 osservazioni = 17 curve uniche. La matrice 2×2×2 non aggiunge
  evidenza: è un moltiplicatore di righe, non di informazione.

Entrambi i difetti sono già mitigati dal "N onesto" (Fase 5b) e dal campo
"Curve uniche" nei report, ma la regola va resa strutturale (vedi §3).

### Asse 3 — Costi: AGGRAVANTE, non causa

- Costo esecuzione mediano per finestra: 0.23%–0.79%
  (`median_execution_cost_ratio` nei report candidati; roc_momentum il
  peggiore a 0.79%, coerente col suo turnover).
- Il confronto decisivo del walk-forward (S_test vs BH_S) è *lordo*
  (segnale puro, senza cost model): anche così, tutti i segnali stanno
  sotto il buy&hold. **I costi peggiorano un verdetto già negativo, non
  lo creano.**
- Impatto sul futuro: l'alpha residuo lordo misurato è +2.3%..+6.1% annuo;
  netto dei costi scende verso lo zero. Questo numero è l'input critico
  del modello economico S0.2: un alpha che non copre i costi non è un
  business.

### Asse 4 — Benchmark: LA CAUSA PRINCIPALE (misuravamo la cosa sbagliata)

Il finding più importante dell'autopsia:

- Tutti e 3 i segnali trend hanno **luck p < 0.1 out-of-sample**
  (0.004–0.072): l'edge *esiste* e non è rumore. Ma è edge **contro il
  caso**, non **contro il mercato**.
- S_test (+0.74..+1.33) < BH_S (+1.35 ES, +1.40 SPY, +0.86 BTC) su tutta
  la linea: lo Sharpe alto era **beta** — un mercato rialzista (test
  2023-26) premia chiunque stia long. I nostri segnali erano "buy&hold
  imperfetti": stessa esposizione direzionale, Sharpe e ritorno inferiori,
  hit rate 21-48%. Unico vantaggio: drawdown minore (7.7%–8.9% su ES/SPY
  vs 18.5%–18.8% del tenere; 29.6%–40.4% BTC vs 53%) perché ogni tanto
  stanno flat — ma un long-passivo con DD minore e Sharpe minore resta
  beta impacchettato, non un business.
- Il closeout M31 del 2026-07-19 (APPROVED, Sharpe 1.01) era probabilmente
  fatto della stessa sostanza: Sharpe assoluto in finestra favorevole =
  beta, non alpha. Il gate originale misurava performance assoluta; la
  correzione ADR-016 (anti-beta: S_test > BH_S) è ciò che ha reso visibile
  la verità.

**Diagnosi: per mesi abbiamo misurato la temperatura con un termometro
tarato sul mercato rialzista. La strategia non è morta di malattia; il
metro con cui la dichiaravamo viva era sbagliato.** Ora il metro è
corretto (anti-beta, N onesto) e il verdetto è coerente su 4 fasi
indipendenti.

### Asse 5 — Orizzonte: INCOMPATIBILE con l'obiettivo economico

- Orizzonte testato: daily (1d), finestre ~1000 bar (~4 anni), segnali
  long/flat a basso turnover. Il test out-of-sample della Fase 2 è
  ~3.6 anni per ES/SPY (902/897 bar) e ~5.2 anni per BTC (1312 bar):
  non cortissimo, ma interamente in un macro-regime rialzista, quindi
  non discrimina i segnali.
- Il canale prop-firm (€3K/mese, trailing DD, consistency rule) richiede
  *flusso di cassa mensile con drawdown contenuto*. Un segnale long-only
  daily su ES non produce quella cadenza: sta long mesi interi (beta) o
  flat, e quando perde lo fa in finestre che violano il DD 4%
  (8/8 candidati sopra il tetto nel gate di Fase 5c).
- Evidenza indiretta: il paper run G6-WP2 ha prodotto **0 trade in 30/30
  sessioni** (BL-024) — il segnale si attiva troppo raramente per
  l'orizzonte operativo del firm. Orizzonte e canale confliggono: questo
  è esattamente il rischio "channel constraints" che S0.5 deve
  quantificare.

### Asse 6 — Regime: NON DIMOSTRATO, ipotesi ancora aperta (con cautela)

- M31 Fase 5 perde in 5/6 regimi; unico positivo: liquidity_shock +0.36%
  (sotto la soglia di significatività pratica).
- Mean-reversion (4 candidati) negativa in *tutti* i regimi, luck p=1.0:
  su ES daily la family è da considerare morta.
- Il regime filter era la lead idea di S1.1, ma il classificatore M32a era
  biasato (29/30 sessioni "choppy"): **il regime filter è la lead idea SOLO
  dopo il post-mortem del classificatore**, come già vincolato nel piano.
- Il regime resta l'unica via non falsificata per estrarre l'alpha residuo
  (+2-6% lordo), ma il §3 sotto spiega perché probabilmente non basta.

## 2. Verdetto sintetico per asse

| Asse | Verdetto | Peso nella morte |
|---|---|---|
| Dati | Non colpevole | — |
| Implementazione | Assolta (2 difetti registrati) | — |
| Costi | Aggravante | secondario |
| Benchmark | **Causa principale** (misuravamo beta come alpha) | primario |
| Orizzonte | Incompatibile col canale prop-firm | primario |
| Regime | Non dimostrato, aperto con cautela | residuo |

**Sintesi in una frase:** la strategia non aveva alpha; aveva beta
nascosto da un benchmark sbagliato, su un orizzonte incompatibile con il
canale economico obiettivo, in uno spazio (fattori TA pubblici su ES
daily) istituzionalmente affollato — 0/9 è il base rate atteso, non
sfortuna.

## 3. Lezioni vincolanti per S1 (da non ripetere)

1. **Ogni nuovo candidato deve passare un test di indipendenza** prima di
   entrare nel gate: stessa matematica sotto nomi diversi = stessa
   ipotesi (caso bollinger/zscore). Il trial ledger di S0.3 deve
   registrare la *definizione* dell'ipotesi, non solo il nome.
2. **Le varianti devono essere economicamente distinte o dichiarate come
   un'unica curva.** La matrice 2×2×2 attuale non genera evidenza: o si
   cablano differenze reali (sizing, exit, filtri) o il report conta 1
   curva, non 8.
3. **Nessun verdetto di vita su Sharpe assoluto.** Anti-beta
   (S_test > BH_S) è obbligatorio in ogni gate futuro (già in ADR-016;
   confermato da questa autopsia come causa principale del falso APPROVED
   del 19-lug).
4. **Mean-reversion su ES daily: archiviata** (4/4 candidati negativi,
   luck p=1.0). Non riprovare senza un'ipotesi nuova e pre-registrata.
5. **L'alpha residuo trend (+2-6% lordo) è il soffitto misurato di questo
   spazio**: anche il regime filter perfetto parte da lì, e netto costi
   tende a zero. È l'input di S0.2 — se il modello economico richiede più
   di così, la lane ricerca va chiusa indipendentemente da quanti altri
   segnali proviamo (meta-kill rule del piano).
6. **Prima di estendere il lake (S1.3), questa diagnosi doveva esistere.**
   Ora esiste: nessuna estensione dati è giustificata per risuscitare le
   family morte.

## 4. Azioni derivanti (input per il backlog)

- [x] Questo report chiude S0.1 (diagnosi).
- [ ] Deduplicare `zscore_reversion`/`bollinger_reversion` nel registry
  candidati (o dichiararli alias espliciti) — anti-Difetto A.
- [ ] Il runner di qualifica deve riportare "curve uniche" come N
  ufficiale del gate in *tutti* i report (oggi lo fa solo il rerun
  finale) — anti-Difetto B.
- [ ] Post-mortem del classificatore di regime M32a (prerequisito S1.1,
  già nel piano).
- [ ] S0.2 deve usare +2-6% lordo come alpha di riferimento per il conto
  economico (non il gross Sharpe delle singole finestre).

## Fonti (evidenza versionata nel repo)

| Evidenza | File |
|---|---|
| M31 closeout 19-lug (APPROVED poi invalidato) | `docs/reports/2026-07-19-m31-closeout.md` |
| Re-run canonico 30-lug (REJECTED, Sharpe -1.15, DD 12.7%) | `docs/reports/m31-historical-replay-qualification.{json,md}` |
| Fase 5/5b: numeri onesti (Sharpe -0.251/-0.31) | BACKLOG.md §G5 (BL-023 Fasi 5/5b) |
| Note diagnosi post-fix 25-lug | `docs/reports/m31-rerun/notes.md` |
| Sweep 8 candidati (Fase 5c) | `docs/reports/candidates/*.{json,md}` |
| Walk-forward multi-asset (Fase 2) | `docs/reports/multiasset/walkforward.{json,md}` |
| G6-WP2 0 trade / 0 P&L | BACKLOG.md BL-024 |
| Classificatore biasato 29/30 choppy | `docs/G6-PAPER-ANALYSIS.md` |
| Classi segnale (duplicato trovato) | `analytics/strategy/signals.py:82,202` |
| bbands ddof=0 | `analytics/technical/polars_indicators.py:100` |
| Piano production-grade S0.1 | `docs/plan-production-grade.md` (commit `3bdef58`) |
