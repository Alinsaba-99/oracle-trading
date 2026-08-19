# 04 Order flow — Literature Review

> Fonti: Tavily API (advanced, AI-optimized) 2026-08-17. URL verified.

## 1. Auction Market Theory (AMT)

### Steidlmayer 1987 — Market Profile origin

**Book**: Steidlmayer, J.P. (1987). *Market Profile and Liquidity Data Research*.

- **Market Profile**: visualizzazione a campana del prezzo nel tempo. TPO (Time Price Opportunity) = 30 min bracket.
- **Value Area**: 70% del TPOs (1 std dev). Fair value zone.
- **POC (Point of Control)**: price con più TPO. Più fair.

### Dalton 1991 — Mind Over Markets

**Book**: Dalton, J. (1991). *Mind Over Markets: Understanding the Auction Process*.

- **Auction process**: buyers + sellers compete per facilitare trade. Fair value è dynamic.
- **Day types**: Normal Day, Trend Day, Double Distribution, Non-Fair Exchange.
- **Reading order**: dove è ora vs dove era. Acceptance vs rejection at POC.

### CBPVA Volume Profile

- **Volume Profile** = Market Profile con volume instead of TPO.
- **Value Area Volume**: 70% del volume.
- **High/Low Value Area** = support/resistance. Reject = reversal.
- **Trend Day**: volume migrate in una direzione, POC shifts each session.
- **Liquidity void**: gap tra Value Areas = future target magnet.

## 2. Footprint charts + delta

### Footprint chart components (AlgoStorm ref)

- **Bid column (left)**: aggressive sellers hitting bid.
- **Ask column (right)**: aggressive buyers lifting ask.
- **Delta** = ask volume - bid volume. Net aggression per candle.
- **Cumulative Delta**: running total session. Trend di aggressione.
- **POC per candle**: price con max volume in quella candle.
- **Imbalance**: extreme diagonal disparity. Threshold 3-4x ratio + min absolute (50-200 contracts ES).
- **Stacked imbalances**: multiple imbalances same side = strong signal.

### Order flow patterns

- **Absorption**: high delta opposite to price direction. Es: price up, delta negative → sellers absorbing.
- **Exhaustion**: delta fading at extremes. Cumulative delta non fa new high con price = divergence.
- **Initiative vs Responsive**: initiative = aggression nel trend; responsive = fade al limite.

## 3. Order flow imbalance academic

### Cont-Brown 2008

**Paper**: Cont, R., Brown, P. (2008). *Order Flow Imbalance and Returns*.

- **OFI (Order Flow Imbalance)** = net of bid/ask updates weighted.
- **Predictive**: OFI predicts short-term returns (next 5-10 min).
- **Magnitude**: R² ~30-40% su 10-minute horizon.
- **Reversion**: effects decay over 30-60 minutes.

### Cao-Hansch-Wang 2008/2009

**Paper**: Cao, C., Hansch, O., Wang, X. (2008). *Order Placement Strategies in a Pure Limit Order Book*. + (2009) *The Information Content of an Open Limit-Order Book*.

- **Limit order book** ha information content predictivo.
- **Order placement strategies**: limit orders shape future price discovery.
- **Chinese markets**: OFI has negative predictive power (contrarian) in alcuni regimi.

### Baruch 2005

**Paper**: Baruch, S. (2005). *Who Benefits from an Open Limit-Order Book?*

- **Transparency effect**: open limit order book → better price discovery + tighter spreads.
- **Implication**: L2 visibility è valore (edge per chi ce l'ha).

## 4. L2 data sources (data audit)

### Crypto L2 — FREE $0

- **Binance public WebSocket**: `wss://fstream.binance.com/public/stream` per futures. `wss://stream.binance.com:9443` per spot. Depth updates 100ms. NO API key.
- **Binance Vision historical**: `https://data.binance.vision` — bulk CSV `data-streams/depthsnapshots`. Free no auth.
- **Deribit public WebSocket**: `wss://www.deribit.com/ws/api/v2` — full L2 snapshot + increments. Free no auth.
- **BitMEX public WebSocket**: `wss://www.bitmex.com/realtime` — L2 depth. Free no auth.
- **OKX public WebSocket**: `wss://ws.okx.com:8443/ws/v5/public` — L2 depth + trades. Free no auth.

### US equities L2 — PAYWALLED

- **Nasdaq TotalView** via IBKR: $48/mo. Waived se commissioni >$48/mo.
- **NYSE OpenBook** via IBKR: $25/mo.
- **NYSE ArcaBook** via IBKR: $11/mo.
- **OPRA options L1** via IBKR: $1.50/mo. (utente già ha — vedi memoria IBKR Gateway).
- **OTC Markets L2** via IBKR: $20/mo.
- **Total US L2** ≈ $75-100/mo per data feed.

### US futures L2 — PAYWALLED

- **CME Globex L2**: ~$10-30/mo per CME Data Package (depth + trades).
- **IBKR Paper Gateway**: NON include L2, solo L1.
- **CME E-mini ES futures L2**: paywalled, no free tier.

### Crypto L2 historical (paywalled per tick-level storico)

- **Tardis.dev**: $350/mo+ per derivatives exchanges historical tick L2.
- **Databento**: OUT (carta italiana rifiutata — vedi `databento-out` memory).
- **Crypto-Lake free tier**: alcuni L2 tick free. `lakeapi` Python package.

## 5. Cap summary

**Edge forte ma hard-blocked per US**:
- Auction Market Theory (Steidlmayer + Dalton) — methodology robusta ma richiede L2.
- Volume Profile + POC — utilizzabile anche con L1 (volume per price livello).
- Footprint charts — richiede L2 tick-by-tick.
- Order Flow Imbalance (Cont-Brown) — richiede L2 + trade classification (Lee-Ready).

**Edge available FREE su crypto**:
- Binance BTCUSDT perp L2 free → footprint + delta + imbalance per crypto futures.
- Volume Profile su crypto spot (Binance Vision bulk) free.

**Edge partial con L1 only**:
- Volume Profile da yfinance daily → rough (1 bar = 1 day, no intra-bar volume distribution).
- OBV (On Balance Volume) — proxy of aggression, no L2 needed.
- VWAP deviation — proxy of fair value, no L2.

## 6. Books reference

- **A Complete Guide to Volume Price Analysis** (Anna Coulling) — practical guide VPA. Amazon $20 paperback, Kindle ~$10.
- **Mind Over Markets** (Jim Dalton) — Market Profile reference. Out of print, used $80-150.
- **Steidlmayer on Markets** (Steidlmayer) — CBPVA + Liquidity Data Bank. Out of print.
- **Aerospace Trades**: institutional order flow references. Paid subscriptions.
