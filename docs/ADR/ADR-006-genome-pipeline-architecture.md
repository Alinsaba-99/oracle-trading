# ADR-006: Genoma come Pipeline Decisionale

**Data:** 2026-07-06
**Status:** ACCEPTED

---

## Context

Il cuore del Genetic Engine di Oracle: come rappresentare una strategia come genoma evolvibile.

Approcci:
1. **Rule-based**: IF RSI < 30 THEN BUY. Interpretabile ma rigido.
2. **Neural weights**: Vettore di pesi per strategia template. Flessibile ma black-box.
3. **Pipeline**: Il genoma definisce una pipeline di moduli. Ogni modulo ha geni indipendenti.

## Decision

Usare **Pipeline Approach** con 6 moduli:

```python
Genome = {
    universe_genes:   # COSA screenare (Nasdaq100, SmallCap, Crypto L1, etc.)
    feature_genes:    # COME trasformare i dati (indicatori, pesi, transforms)
    signal_genes:     # COME generare segnali (scoring, soglie, timeframe)
    filter_genes:     # QUANDO non operare (FOMC, earnings, spread, vol, regime)
    risk_genes:       # QUANTO rischiare (sizing, SL, TP, trailing, VaR)
    execution_genes:  # COME eseguire (algo, urgency, slippage model)
}
```

## Rationale

- Ogni modulo è un sottoproblema separato, evolvibile indipendentemente
- Pipeline chiara: Universe → Feature → Signal → Filter → Risk → Execution
- Il GA può ottimizzare COSA cercare (universe) prima di COME cercarlo (signal)
- I filtri (filter_genes) sono spesso più importanti degli indicatori
- La separazione permette crossover e mutazione a livello di modulo
- Interpretabile: ogni decisione è tracciabile a un modulo specifico

## Consequences

- Il genoma non produce una strategia: produce una pipeline decisionale completa
- Ogni modulo può avere sotto-geni con encoding diverso
- Crossover e mutazione operano a livello di modulo prima che di gene
- FilterGenes include: FOMC, earnings, spread, vol, volume, regime, liquidity
- UniverseGenes evolverà universi sempre più specifici
- Le strategie evolute sono esportabili come plugin
