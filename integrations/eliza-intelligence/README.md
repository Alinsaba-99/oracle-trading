# Oracle Eliza Intelligence Bridge

Read-only elizaOS plugin that publishes evidence-backed alternative-market
observations to Oracle's API gateway.

## Security boundary

The plugin can:

- collect social, news, ecosystem and on-chain observations;
- attach source timestamps, hashes and credibility scores;
- publish observations to `POST /api/v1/intelligence/observations`;
- receive outcome feedback in later iterations.

The plugin cannot:

- access broker credentials;
- place, cancel or amend orders;
- modify the portfolio ledger or prop-firm rule profiles;
- disable risk checks or kill switches.

Oracle remains the system of record. Observations must pass through the
Investment Committee, deterministic risk kernel and OMS before they can affect
a portfolio.

## Version policy

The bridge pins `@elizaos/core` to `1.7.2`, matching the current stable 1.x
plugin ecosystem. The upstream develop branch is on a separate 2.x beta line,
so upgrades require an explicit compatibility and security review.

The current upstream dependency graph reports low-severity cryptography
advisories inherited through browser compatibility packages. This bridge does
not expose wallets or cryptographic signing, and CI fails on high or critical
production advisories. A clean audit remains a promotion gate before enabling
additional Eliza plugins.

## Commands

```bash
npm ci
npm run typecheck
npm run test
npm run build
npm audit --omit=dev --audit-level=high
```

## Eliza usage

```ts
import {
  createOracleIntelligencePlugin,
  HttpOraclePublisher,
} from "@oracle/eliza-intelligence";

const publisher = new HttpOraclePublisher(
  "http://oracle-api:8000/api/v1/intelligence/observations",
  process.env.ORACLE_API_KEY,
);

export const oraclePlugin = createOracleIntelligencePlugin(publisher);
```
