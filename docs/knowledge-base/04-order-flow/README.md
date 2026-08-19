# Dominio 04 — Order flow / L2 / footprint

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.
> **Dominio hard-blocked per US equities + futures** — gap dichiarato onesto.

## Sintesi esecutiva

L'analisi order flow è **top-tier istituzionale** ma con restrizioni dati severe sotto $0/mo:

1. **Auction Market Theory** (Steidlmayer 1987 + Dalton 1991 *Mind Over Markets*): mercati come aste continue bidirezionali. Fair value determinato da 70% Value Area. POC (Point of Control) = price con max volume. Più tempo a price = più fair.
2. **Volume Profile** (Steidlmayer CBPVA 2003): bell-shaped curve. Value Area = 1 std dev (68% del volume). POC = peak. Reject High/Low Value Area = support/resistance.
3. **Footprint charts** (AlgoStorm ref): bid vs ask volume per price per candle. Delta = ask - bid. Cumulative Delta = trend di aggressione. Imbalances (3-4x ratio) = stacked aggression.
4. **Order flow imbalance** (Cont-Brown 2008, Cao-Chen 2009): OFI predice short-term returns ma reverte lungo. Inventory effects importanti.
5. **Cao-Hansch-Wang 2009**: open limit-order book ha information content. Limit orders shape price discovery.

**Verdetto hard-blocked**:
- **US equities L2**: Nasdaq TotalView $48/mo via IBKR (Commission waived se >$48 commissioni/mese), NYSE OpenBook $25/mo, OPRA options $1.50/mo. Total ≈ $75-100/mo per US L2.
- **US futures L2 (CME Globex)**: ~$10-30/mo per CME Data Package. IBKR Paper Gateway NON include L2.
- **Crypto L2**: **FREE $0** via Binance public WebSocket (`wss://fstream.binance.com/public/stream`) — depth updates 100ms. Deribit/BitMEX full L2 snapshots free. Tardis.dev paywalled ($350/mo+ per historical).
- **Lake API / Crypto-Lake free tier**: L2 tick-level per crypto, free download.

**Cap to build su crypto only**:
1. Binance Vision L2 historical (bulk CSV, no auth) — `data-streams/depthsnapshots` per BTCUSDT
2. Binance WebSocket L2 real-time — going forward capture
3. Footprint + Volume Profile su crypto futures (BTCUSDT perp) dove dati sono free
4. **Lane F crypto order flow** nuova — strategia crypto-specific

**Hard-blocked per Oracle US equities + futures**: L2 dati paywalled. Gap dichiarato in ADR-020. Lane A (SPY 1h) + Lane D (VRP) NON possono avere order flow signal real. Lane B (value equity) non necessita L2.

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
