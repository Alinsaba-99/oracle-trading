# Ricerca "Miracoli" — Progetti e Papers per potenziare Oracle

> 2026-07-29 | Ricercati 20+ progetti da awesome-systematic-trading + Kairos-v2

---

## I 4 progetti PIU' PROMETTENTI per Oracle

### 1. FinClaw (12.1K⭐) — Evoluzione Genetica di Strategie

https://github.com/NeuZhou/finclaw

| Cosa fa | Cosa dà a Oracle |
|---------|------------------|
| 484 fattori built-in (factor zoo) | +415 fattori rispetto ai nostri 69 |
| GA (Genetic Algorithm) evolution loop | Strategie che si evolvono DA SOLE |
| Walk-forward validation integrato | Già lo abbiamo, ma loro lo applicano ad ogni generazione |
| Multi-market (US, CN, crypto) | Pipeline già pronta |

**Come integrarlo**: Non serve copiare FinClaw. Basta prendere i loro **484 fattori** e passarli al nostro WeightEvolver + AdaptiveEnsemble. I fattori sono formule (come Alpha101) — li traduciamo in `signals_r3.py`.

**Edge che sblocca**: Se ora abbiamo 4 specialisti con edge su 4 asset, con 484 fattori possiamo avere edge su 50+ asset. La GA evolution loop trova automaticamente le combinazioni migliori.

---

### 2. Kairos-v2 — ML Regime Classifier (PyTorch ResBlock)

https://github.com/PVinh-Quant/Kairos-v2

| Cosa fa | Cosa dà a Oracle |
|---------|------------------|
| PyTorch ResBlock MLP per regime classification | 8 regimi invece di 4 (molto più granulare) |
| 49 indicatori su 8 timeframe | Feature engineering pipeline multi-tempo |
| Bayesian hyperparameter optimization | Ottimizzazione parametri automatica |
| Anti-leakage MTF engine | Allineamento multi-timeframe senza look-ahead |

**Come integrarlo**: Prendere il loro **regime classifier** (ResBlock MLP, ~100 righe di PyTorch) e usarlo AL POSTO del nostro EnsembleVoter SMA-heuristic. Un modello PyTorch che classifica 8 regimi invece di 4 darebbe routing molto più preciso.

**Edge che sblocca**: Il regime detector attuale ha 56% di "choppy" — troppo conservativo. Con 8 regimi, possiamo discriminare tra "choppy_range", "choppy_trending" e "choppy_volatile", ognuno con uno specialista diverso.

---

### 3. FinRL (AI4Finance, 10.3K⭐) — Deep Reinforcement Learning

https://github.com/AI4Finance-Foundation/FinRL

| Cosa fa | Cosa dà a Oracle |
|---------|------------------|
| Deep RL per portfolio optimization | Pesi imparati, non fissati |
| 20+ algoritmi (PPO, SAC, DQN, A2C) | Allenamento su dati storici |
| Market data → State → Action → Reward | Ciclo completo di apprendimento |

**Come integrarlo**: Non serve l'intero framework. Basta usare il **DRL-based portfolio optimizer** per sostituire il nostro HRP statico. L'agente RL decide i pesi tra specialisti in tempo reale basandosi sullo stato di mercato attuale, non su una matrice pre-calibrata.

**Edge che sblocca**: HRP usa correlazioni storiche fisse. DRL si adatta in tempo reale ai cambiamenti di correlazione.

---

### 4. ai-hedge-fund (14K⭐) — Multi-Agent LLM Trading Team

https://github.com/virattt/ai-hedge-fund

| Cosa fa | Cosa dà a Oracle |
|---------|------------------|
| Multi-agent LLM: CEO + Analyst + Trader + Risk | Framework agenti già testato |
| Ogni agente ha un ruolo specifico | Pattern per orchestrare i nostri 4 specialisti |
| LLM decide entry/exit con ragionamento | Non solo segnale numerico ma spiegazione |

**Come integrarlo**: Oracle ha già 4 specialisti (trend, mean_rev, breakout, lorentzian). Il pattern multi-agent di ai-hedge-fund dà la struttura per farli ragionare e VOTARE invece di rutare binaramente. Ogni specialista produce un segnale + una confidence, e un meta-agent (LLM o rule-based) decide il peso finale.

---

## Tabella d'impatto

| Progetto | Sforzo integrazione | Edge improvement | Priorità |
|----------|:------------------:|:----------------:|:--------:|
| **FinClaw** (484 fattori) | 1 settimana | Molto alto | **P0** |
| **Kairos-v2** (ML regime) | 3 giorni | Alto | **P1** |
| **FinRL** (DRL portfolio) | 2 settimane | Medio | P2 |
| **ai-hedge-fund** (multi-agent) | 1 settimana | Medio | P2 |

---

## Raccomandazione

**P0 immediato**: FinClaw — prendere i 484 fattori come `signals_r3.py`. Con 484 fattori, il WeightEvolver ha abbasta materiale per trovare edge su 50+ asset invece di 4. È il moltiplicatore più alto con lo sforzo più basso.

**P1 subito dopo**: Kairos-v2 — PyTorch regime classifier a 8 regimi. Serve per dare ai 484 fattori un routing preciso invece del choppy-biased attuale.

Questi due insieme potrebbero portare il portfolio da 4 edge a 50+ edge, trasformando Oracle da "sistema con qualche edge" a "fabbrica di edge automatica".
