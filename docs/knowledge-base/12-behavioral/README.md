# Dominio 12 — Behavioral / bubble / panic

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.

## Sintesi esecutiva

La finanza comportamentale è **framework teorico** ma con alcuni signal tradabili:

1. **De Bondt-Thaler 1985** — long-term reversal. Loser portfolios (3-5y) outperform winner portfolios. Asymmetric (stronger in January). Due to overreaction.
2. **Kahneman-Tversky 1979** — prospect theory. Loss aversion (~2.25x). Risk-seeking in losses, risk-averse in gains.
3. **Shiller 2000** — *Irrational Exuberance*. CAPE ratio predicts bubbles. Predicted 2000 dotcom bubble.
4. **Taleb 2007 + 2012** — Black Swan + Antifragile. Barbell strategy: 90% safe + 10% convex bets. Tail risk convexity.
5. **Greenwood-Shleifer 2014** — extrapolative expectations. Investors over-extrapolate past returns. Bubble formation mechanism.
6. **Jegadeesh-Titman 1993** — momentum (opposite of De Bondt-Thaler at 3-12m horizon). Behavioral underreaction.
7. **Barberis 2018** — bubbles + extrapolation formal model. Combines Greenwood-Shleifer with behavioral theory.

**Cap to build Oracle**:
1. De Bondt-Thaler reversal signal (3-5y horizon)
2. Behavioral bubble detector (CAPE + sentiment + extrapolative surveys)
3. Taleb barbell tail-risk overlay
4. Loss aversion position sizing (Kahneman-Tversky)

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
