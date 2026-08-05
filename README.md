# Oracle — Systematic Trading Intelligence Platform

Multi-agent platform for systematic trading research and execution. Specialized
agents (analysts, decision, debate, committee, oracle) coordinate across research,
analytics, and execution planes. Experiments are governed by ADRs and walk-forward
benchmarks with documented verdicts — including the rejections.

**Status: research.** No funded capital. Execution is paper/replay only.
The codebase is a modular monolith in evolution, not a set of microservices —
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) describes the current state as it is,
not as it should be.

## Repository layout

| Path | Purpose |
|------|---------|
| `agents/` | Agent orchestration: analysts, decision, debate, committee, oracle |
| `analytics/` | Regime detection, macro data (FRED/FX), strategy qualification |
| `execution/` | Paper broker, broker adapters, order management, policy engine |
| `genetics/` | Evolutionary strategy search (DEAP) |
| `experiments/` | Walk-forward runs and ADR-governed experiment verdicts |
| `core/` | Domain model, events, configuration, audit |
| `apps/` | CLIs and services |
| `docs/` | ADRs, architecture, data sources, governance, audits |

## The experiment process

Every result is a documented verdict, not a headline. Examples from the commit
history:

- **Rejected**: multi-asset walk-forward (ES/SPY/BTC) on trend winners —
  0/9 asset×signal combinations beat buy&hold; measured alpha of 2-6%/yr was
  beta, not edge.
- **Autopsy**: post-mortem of a failed benchmark — root cause was beta misread
  as alpha due to an incompatible horizon; two defects registered, fixed in ADR.
- **Honest N**: sample sizes stated explicitly in ADRs; small-N results are
  labeled as such.

Negative results are first-class artifacts. If a strategy does not work, that
is a finding, not a failure.

## Quickstart

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # fill real values — .env is gitignored
oracle --help
```

Runtime modes (set via `.env`): `research`, `replay`, `paper`, `shadow`,
`evaluation`, `funded`. Research and replay need no credentials.

## Security

- `.env` is gitignored; real credentials are never committed
  (`scripts/check_credentials.sh` verifies after rotations)
- `.gitleaks.toml` defines secret-scanning rules for CI
- Experiment artifacts and checkpoints are gitignored and regenerable

## License

MIT
