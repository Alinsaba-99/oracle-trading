"""BL-701/702 — Edge Research Factory registry builder.

Deterministic: embeds the mined hypotheses (KB 13 domains + MoonDev
practitioner factors) and regenerates every YAML in
docs/knowledge-base/edge-factory/registry/.  Run:

    uv run python scripts/build_edge_factory_registry.py

Hypotheses were extracted 2026-08-22 from docs/knowledge-base/<dominio>/
(README/edge/literature), docs/knowledge-base/AUDIT-2026-08-17.md and
trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md.  See the factory
design spec §3 (docs/plans/2026-08-21-edge-research-factory-design.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analytics.research.factory.registry import (  # noqa: E402
    DomainRegistry,
    Evidence,
    Hypothesis,
    save_registry,
)

REGISTRY_DIR = REPO_ROOT / "docs" / "knowledge-base" / "edge-factory" / "registry"

KB = "docs/knowledge-base"
MD = "trading-os/knowledge/moondev-repos"


def _ev(kb_path: str, testo: str) -> list[Evidence]:
    return [Evidence.now("miner", testo, ref=kb_path)]


def _kb(
    nome: str,
    meccanismo: str,
    perche: str,
    fonti: list[str],
    dati: list[str],
    assets: list[str],
    timeframe: list[str],
    decay: float = 30.0,
    effect: str = "non_quantificata",
    dati_posseduti: bool | None = None,
    hid: str = "EF-000",
) -> Hypothesis:
    return Hypothesis(
        id=hid,
        nome=nome,
        meccanismo=meccanismo,
        perche_esiste=perche,
        origine="kb",
        fonti=fonti,
        effect_size_dichiarata=effect,
        decay_atteso_pct=decay,
        dati_richiesti=dati,
        dati_posseduti=dati_posseduti,
        asset_candidati=assets,
        timeframe=timeframe,
        stato="da_amplificare",
        evidenza=_ev(fonti[0], f"estratta da {fonti[0]}"),
    )


def _md(
    nome: str,
    meccanismo: str,
    perche: str,
    fonti: list[str],
    dati: list[str],
    assets: list[str],
    timeframe: list[str],
    decay: float,
    dati_posseduti: bool | None = None,
    hid: str = "EF-000",
) -> Hypothesis:
    return Hypothesis(
        id=hid,
        nome=nome,
        meccanismo=meccanismo,
        perche_esiste=perche,
        origine="practitioner",
        fonti=fonti,
        effect_size_dichiarata="non_quantificata",
        decay_atteso_pct=decay,
        dati_richiesti=dati,
        dati_posseduti=dati_posseduti,
        asset_candidati=assets,
        timeframe=timeframe,
        stato="da_amplificare",
        evidenza=[
            Evidence.now(
                "miner", "fattore triaged MoonDev; claim di rendimento NON verificato", ref=fonti[0]
            )
        ],
    )


DOMAINS: dict[str, list[Hypothesis]] = {
    # ---------------------------------------------------------------- 01
    "01-fundamental": [
        _kb(
            nome="novy-marx-gross-profitability",
            meccanismo="aziende con alto profitto lordo su asset (GPA) SOPRAPERFORMANO le attese: gross profitability è un fattore di qualità che predice rendimenti cross-sectional mensili oltre value (long alto GPA)",
            perche="costi di ingresso/uscita e vantaggi competitivi persistenti generano profitti stabili che il mercato sconta troppo lentamente (friction del capitale fisico)",
            fonti=[f"{KB}/01-fundamental/README.md"],
            dati=[
                "SimFin income statement + balance sheet (185 ticker)",
                "prezzi EOD SimFin/yfinance",
            ],
            assets=["US equities SimFin 185 ticker"],
            timeframe=["1M rebalance"],
            effect="documentata in Novy-Marx 2013 (gross profitability premium)",
        ),
        _kb(
            nome="piotroski-fscore-value-long",
            meccanismo="F-Score 9 punteggi (ROA, accruals, leverage, margin...) dentro il decile value separa i value-trap dai recuperabili: long high-F value stocks, rebalance annuale",
            perche="mercato punisce troppo le azioni svalutate per inattenzione; i segnali contabili ravvicinano la correzione dell'underpricing",
            fonti=[f"{KB}/01-fundamental/README.md"],
            dati=["SimFin fundamentals", "prezzi EOD"],
            assets=["US equities SimFin"],
            timeframe=["1Y rebalance"],
            effect="+13.4% annuo su high-F value stocks (Piotroski 2000, pre-decay)",
        ),
        _kb(
            nome="sloan-accrual-anomaly",
            meccanismo="aziende con accruals elevati (utile cash-flow < utile contabile) hanno rendimenti futuri inferiori: short high-accrual / long low-accrual, decili mensili",
            perche="gli investitori ancorano all'earnings totale e ignorano la componente accrual meno persistente (naive expectations)",
            fonti=[f"{KB}/01-fundamental/README.md"],
            dati=["SimFin cashflow + income statement", "prezzi EOD"],
            assets=["US equities SimFin"],
            timeframe=["1Q signals, 1M rebalance"],
        ),
        _kb(
            nome="value-momentum-everywhere",
            meccanismo="combo value + momentum 8 asset class: segnali value (book-to-price) e momentum (12-1) cross-sectional su indici/ETF multi-asset, long top-quintile / short bottom",
            perche="premi comuni a rischio di liquidità e comportamentali emergono in ogni classe di asset (Asness-Moskowitz-Pedersen 2013, BL-KB-103)",
            fonti=[f"{KB}/AUDIT-2026-08-17.md", f"{KB}/01-fundamental/README.md"],
            dati=[
                "ETF EOD multi-asset (lake/yfinance: SPY, IEF, DBC, UUP, GLD...)",
                "SimFin fundamentals per la parte equity",
            ],
            assets=["SPY/IEF/DBC/UUP/GLD/USO + SimFin equities"],
            timeframe=["1M rebalance"],
        ),
    ],
    # ---------------------------------------------------------------- 02
    "02-macro": [
        _kb(
            nome="output-gap-equity-risk-premium",
            meccanismo="output gap negativo (produzione sotto trend HP-filter) predice excess returns futuri di azioni e bond a 1 anno; long risk asset quando gap negativo",
            perche="la politica monetaria accommoda e la confluenza di rendimenti spinge premi rischiosi al massimo quando l'economia è deprimuta (Cooper-Priestley 2009)",
            fonti=[f"{KB}/02-macro/README.md"],
            dati=["FRED INDPRO + FEDFUNDS vintage ALFRED (as_of)", "ETF EOD SPY/IEF"],
            assets=["SPY, IEF"],
            timeframe=["1M signal, 1Y orizzonte"],
        ),
        _kb(
            nome="yield-curve-inversion-regime",
            meccanismo="spread 10Y-2Y negativo anticipa recessione con lead 12-18 mesi; de-risking graduale (riduzione equity beta) da inversione confermata 60 giorni",
            perche="il mercato anticipa il ciclo di tagli tassi che segue la recessione attesa; le probabilità di recessione comprimono il multiplo equity con ritardo",
            fonti=[f"{KB}/02-macro/README.md"],
            dati=["FRED DGS10 + DGS2 (T10Y2Y) vintage ALFRED", "ETF EOD SPY"],
            assets=["SPY, IEF"],
            timeframe=["1D signal"],
        ),
        _kb(
            nome="growth-inflation-4regime-allocation",
            meccanismo="classificatore 4 regimi (growth↑↓ × inflation↑↑ su dati PIT) rialloca: stocks in growth↑infl↓, bonds in growth↓infl↓, commodities in growth↑infl↑, cash in growth↓infl↑",
            perche="ogni asset class incassa i flussi ottimali nel proprio regime macro (framework Bridgewater All Weather); le transizioni di regime sono lente e rilevabili su dati PIT",
            fonti=[f"{KB}/02-macro/README.md"],
            dati=["FRED CPIAUCSL + INDPRO vintage ALFRED", "ETF EOD SPY/IEF/DBC/UUP"],
            assets=["SPY, IEF, DBC, UUP"],
            timeframe=["1M rebalance"],
        ),
    ],
    # ---------------------------------------------------------------- 03
    "03-quant": [
        _kb(
            nome="deflated-sharpe-multiple-testing",
            meccanismo="metodo (non segnale): ogni candidato factory con N varianti testate riceve DSR = Φ((SR − SR0)/SE) con SR0 atteso sotto null su N trial; gate DSR ≥ 0.95",
            perche="il massimo di N Sharpe random cresce con N: senza deflazione ogni campione produce falsi champion (Bailey-López de Prado 2014; ADR-017 già adotta)",
            fonti=[f"{KB}/03-quant/README.md"],
            dati=["equity curve dei candidati factory (output runner BL-615)"],
            assets=["tutti i candidati factory"],
            timeframe=["per-candidato"],
        ),
        _kb(
            nome="harvey-liu-zhu-t-threshold",
            meccanismo="metodo (non segnale): un fattore passa solo con t-stat > 3.0 (non 2.0) per il multiple testing su 316+ fattori pubblicati; applicato all'IC t-block dell'IC screen",
            perche="con centinaia di fattori testati l'1% di falsi positivi a t=2 è un esercito; la soglia si alza con il numero di ipotesi (Harvey-Liu-Zhu 2016)",
            fonti=[f"{KB}/03-quant/README.md"],
            dati=["IC screen output (BL-706)"],
            assets=["tutti i fattori factory"],
            timeframe=["per-fattore"],
        ),
        _kb(
            nome="hurst-regime-persistence",
            meccanismo="Hurst exponent > 0.5 (persistent) → strategia trend-following sull'asset; < 0.5 → mean-reversion; stima rolling R/S su finestre 2-4 anni come router di strategia [DUPLICATO di 09-cyclical hurst-rs-regime-router: tenere UNA sola entry in Stage 2 — qui è referenziata come cross-domain]",
            perche="long memory nei rendimenti è documentata e stabile OOS; il market microstructure genera autocorrelazione di segno opposto nei due regimi (Hurst 1951; KB-09)",
            fonti=[f"{KB}/03-quant/README.md", f"{KB}/09-cyclical/README.md"],
            dati=["OHLCV lake (ES 1h, BTCUSDT 1h, FX 1m resample)"],
            assets=["ES, BTCUSDT, EURUSD"],
            timeframe=["1h, 1d"],
        ),
    ],
    # ---------------------------------------------------------------- 04
    "04-order-flow": [
        _kb(
            nome="vpin-l1-informed-trading",
            meccanismo="VPIN (volume-binned probability of informed trading, bulk volume classification con tick rule) alto preannuncia volatilità di prezzo; short-vol/de-risk quando VPIN estremo",
            perche="il flusso informato si accumula prima dei movimenti: la classificazione del volume per bucket sincronizzato rende visibile l'attività informata anche senza L2 (Easley-López de Prado-O'Hara 2012, BL-KB-102 — sblocca il dominio su dati L1 free)",
            fonti=[f"{KB}/AUDIT-2026-08-17.md", f"{KB}/04-order-flow/README.md"],
            dati=[
                "aggTrades o OHLCV+volume 1m (lake BTCUSDT; HistData/IBKR per FX/US in going-forward)"
            ],
            assets=["BTCUSDT, ETHUSDT (crypto ora); EURUSD going-forward"],
            timeframe=["1m → VPIN bucket ~1/50 volume giornaliero"],
            # dati_posseduti false = dati non ANCORA ingesti (aggTrades non scaricati);
            # ingestibile a $0 — sblocco = adapter Vision aggTrades (BL-705 Stage 3)
            dati_posseduti=False,
        ),
        _kb(
            nome="ofi-cont-brown-l2",
            meccanismo="Order Flow Imbalance (net flow ai best quote) predice variazioni di prezzo a orizzonte minuti; strategia momentum-ofi a bassa frequenza di revisione",
            perche="gli ordini aggressivi consumano liquidità e spostano il fair value (Cont-Brown 2008); l'effetto inverte su orizzonti lunghi",
            fonti=[f"{KB}/04-order-flow/README.md"],
            dati=[
                "L2 order book (crypto free via Binance WS; US paywalled $75-100/mo — HARD RULE ADR-020 esclude)"
            ],
            assets=["BTCUSDT perp"],
            timeframe=["tick/100ms → 1m"],
            dati_posseduti=False,
        ),
        _kb(
            nome="cumulative-delta-trend-crypto",
            meccanismo="cumulative delta (ask-bid volume) divergente dal prezzo segnala esaurimento dell'aggressione: price new-high + delta non-confirm → reversal atteso",
            perche="l'aggressione unilaterale esaurisce la liquidità disponibile; la divergenza indica che il movimento non ha più combustibile (footprint/Dalton framework)",
            fonti=[f"{KB}/04-order-flow/README.md"],
            dati=["Binance Vision aggTrades (delta da tick rule), OHLCV 1h lake"],
            assets=["BTCUSDT, ETHUSDT"],
            timeframe=["1h"],
        ),
    ],
    # ---------------------------------------------------------------- 05
    "05-sentiment": [
        _kb(
            nome="baker-wurgler-sentiment-contrarian",
            meccanismo="indice sentiment (closed-end discount, IPO volume, turnover...) alto → sotto pesa small/growth/volatile stocks; long-short decile size/growth con condizione di sentiment",
            perche="l'euforia gonfia i titoli hard-to-arbitrage; il sentiment alto è stato predittore negativo a 1-3y (Baker-Wurgler 2006)",
            fonti=[f"{KB}/05-sentiment/README.md"],
            dati=[
                "FRED/Sentiment proxies free (AAII scraper, CBOE P/C CSV, IPO count proxy)",
                "prezzi decili SimFin/yfinance",
            ],
            assets=["US equities SimFin (small/growth tilt)"],
            timeframe=["1M"],
        ),
        _kb(
            nome="cnn-fear-greed-extreme-contrarian",
            meccanismo="CNN Fear&Greed < 10 (extreme fear) → long SPY orizzonte 3-12m; > 90 non si verifica mai (0 giorni in 10y) → braccio long-only",
            perche="la paura estrema coincide con capitulation e premi rischiosi compressi; statistiche 10y: avg 49 std 20, 16 giorni sotto 10",
            fonti=[f"{KB}/05-sentiment/README.md"],
            dati=["CNN Fear&Greed scraper (chrome-devtools-mcp/curl_cffi)", "SPY EOD lake"],
            assets=["SPY"],
            timeframe=["1D signal"],
        ),
        _kb(
            nome="variance-risk-premium-vrp",
            meccanismo="VRP = VIX² − realized var future: premium alto → attesi rendimenti equity positivi (Bollerslev-Tauchen-Zhou 2009). NOTA: backtest Oracle Lane D reale Sharpe −0.08 (2026-08-17) — serve regime filter + tail cap prima di riprovare",
            perche="la domanda di assicurazione contro la volatilità fa pagare la varianza più del suo valore atteso; il premium compensa chi la vende",
            fonti=[f"{KB}/05-sentiment/README.md"],
            dati=["VIX (FRED VIXCLS)", "SPY 1m/1d per realized var (lake)"],
            assets=["SPY"],
            timeframe=["1M"],
        ),
    ],
    # ---------------------------------------------------------------- 06
    "06-positioning": [
        _kb(
            nome="cot-smart-money-indicator",
            meccanismo="SMI = posizionamento non-commercial relativo ai commercial; estremi commercial long → bottom market (long), estremi spec long crowded → caution. Long-or-flat su futures",
            perche="gli hedger commerciano per business, gli speculatori ineriscono al momentum: gli estremi degli hedger catturano i turn (Bhansali 2014, edge +4-6%/yr dichiarato su commodity)",
            fonti=[f"{KB}/06-positioning/README.md"],
            dati=[
                "CFTC COT historical compressed (free, 1986+)",
                "futures EOD (ES, GC, CL dal lake)",
            ],
            assets=["ES, GC, CL"],
            timeframe=["1W (COT cadence)"],
            effect="+4-6%/yr su commodity (Bhansali 2014, dichiarato dall'autore, pre-decay)",
        ),
        _kb(
            nome="cot-hedging-pressure-deroon",
            meccanismo="hedging pressure (net commercial position normalizzato) forecasta rendimenti futures commodity: long i commodity con pressione hedger più corta",
            perche="i producer-hedger pagano un premio a chi assume il rischio opposto (theory of normal backwardation; De Roon et al 2000)",
            fonti=[f"{KB}/06-positioning/README.md"],
            dati=["CFTC COT", "commodity futures EOD (GC, CL lake; DBC ETF)"],
            assets=["GC, CL, DBC"],
            timeframe=["1M"],
        ),
        _kb(
            nome="open-interest-hong-yogo",
            meccanismo="open interest in crescita con prezzo in crescita = trend sano; OI in calo su rally = short-covering fragile → segnale di uscita",
            perche="l'interesse aperto misura l'impegno nuovo nel trend (Hong-Yogo 2012): i rally senza nuovo OI sono chiusure di short, non posizionamento direzionale",
            fonti=[f"{KB}/06-positioning/README.md"],
            dati=["CFTC COT OI", "OHLCV futures lake"],
            assets=["GC, CL, ES"],
            timeframe=["1W"],
        ),
    ],
    # ---------------------------------------------------------------- 07
    "07-news": [
        _kb(
            nome="google-trends-recession-reversal",
            meccanismo="spike di search volume per 'recession/unemployment/bankruptcy' predice reversal short-term e spike di volatilità nei giorni successivi",
            perche="l'attenzione retail anticipa il panico di vendita e l'aumento di hedging (Da et al 2015); l'informazione di attenzione è misurabile gratis",
            fonti=[f"{KB}/07-news/README.md"],
            dati=["pytrends (Google Trends, free 2004+)", "SPY EOD lake"],
            assets=["SPY, QQQ"],
            timeframe=["1D"],
        ),
        _kb(
            nome="edgar-fulltext-negativity",
            meccanismo="negatività (dizionario Loughran-McDonald) dei filing 10-K/8-K sopra la norma del ticker → drift negativo dei giorni successivi; long-short decili di sentiment",
            perche="il testo dei filing contiene tono informativo che il prezzo assorbe lentamente (Tetlock 2007, Garcia 2013); il dizionario LM è calibrato per il finance",
            fonti=[f"{KB}/07-news/README.md", f"{KB}/AUDIT-2026-08-17.md"],
            dati=["SEC EDGAR full-text API (free, no key)", "prezzi EOD"],
            assets=["US equities"],
            timeframe=["event-driven (filing date)"],
        ),
        _kb(
            nome="wsb-retail-positioning-contrarian",
            meccanismo="top-50 ticker menzionati WSB (Tradestie free) con sentiment estremo unilaterale → fade a 2-5 giorni",
            perche="il crowding retail su singolo nome crea squeeze/overshoot che reverte (Antweiler-Frank 2004 sui message board: i volumi predicono volatilità, non direzione — confutazione attiva in Stage 2)",
            fonti=[f"{KB}/07-news/README.md"],
            dati=["Tradestie/ApeWisdom API (free)", "prezzi EOD"],
            assets=["US equities top-momentum"],
            timeframe=["1D"],
        ),
    ],
    # ---------------------------------------------------------------- 08
    "08-intermarket": [
        _kb(
            nome="stock-bond-correlation-regime",
            meccanismo="correlazione stock-bond 60d che passa da negativa a positiva (inflation regime) → ridurre diversificazione bond, alzare cash/commodities; detector di flight-to-quality breakdown",
            perche="la correlazione negativa vale solo nel regime disinflattivo; il flip 2022 ha reso i bond un hedge inaffidabile (Baur-Lucey 2010 + 2022 flip documentato)",
            fonti=[f"{KB}/08-intermarket/README.md"],
            dati=["ETF EOD SPY+IEF/AGG (lake)", "FRED T10YIE inflation"],
            assets=["SPY, IEF, DBC"],
            timeframe=["1D rolling 60d"],
        ),
        _kb(
            nome="credit-spread-equity-predictor",
            meccanismo="Baa-Aaa spread in allargamento → sotto pesa equity nei mesi successivi (spread alto → rendimenti equity futuri bassi)",
            perche="lo spread credit è il termometro del rischio di default atteso: anticipa il ciclo reale e comprime i multipli con 2-6 mesi di lead",
            fonti=[f"{KB}/08-intermarket/README.md"],
            dati=["FRED BAA_AAAA (vintage ALFRED)", "SPY EOD"],
            assets=["SPY"],
            timeframe=["1M"],
        ),
        _kb(
            nome="sector-rotation-business-cycle",
            meccanismo="classificatore 4 stadi ciclo (expansion/peak/contraction/recovery) → rotazione settoriale con lead 6-9m: tech in expansion, energy in peak, utilities/staples in contraction, financials in recovery",
            perche="i settori hanno sensitività ciclica diversa e il mercato li prezza con ritardo rispetto al ciclo reale (Stovall sector rotation)",
            fonti=[f"{KB}/08-intermarket/README.md"],
            dati=[
                "ETF settoriali EOD (XLK, XLE, XLU, XLP, XLF via yfinance)",
                "FRED INDPRO/CPIAUCSL",
            ],
            assets=["XLK, XLE, XLU, XLP, XLF"],
            timeframe=["1M"],
        ),
    ],
    # ---------------------------------------------------------------- 09
    "09-cyclical": [
        _kb(
            nome="hurst-rs-regime-router",
            meccanismo="Hurst > 0.5 → asset persistent (alloca trend-following); < 0.5 → anti-persistent (alloca mean-reversion); router ricalcolato mensile su 3y rolling",
            perche="la long memory è l'unico ciclo misurabile con rigore nel dominio (Hurst 1951); Elliott/Gann sono soggettivi e scartati, Kondratieff ha troppo poche osservazioni",
            fonti=[f"{KB}/09-cyclical/README.md"],
            dati=["OHLCV lake multi-asset (ES, BTCUSDT, FX)"],
            assets=["ES, BTCUSDT, EURUSD"],
            timeframe=["1d → stima 3y rolling"],
        ),
        _kb(
            nome="fft-spectral-cycle-detector",
            meccanismo="spettro FFT dei rendimenti con picchi persistenti a periodi 40-200 giorni → timing entrata/uscita su quei periodi; se spettro piatto → nessun trade",
            perche="alcuni asset mostrano periodicità debole ma misurabile; il filtro spettrale la quantifica senza le pretese soggettive di Elliott",
            fonti=[f"{KB}/09-cyclical/README.md"],
            dati=["OHLCV 1d lake"],
            assets=["ES, GC, BTCUSDT"],
            timeframe=["1d"],
        ),
    ],
    # ---------------------------------------------------------------- 10
    "10-seasonal": [
        _kb(
            nome="halloween-sell-in-may",
            meccanismo="long SPY 31-ott → 1-mag, flat/cash il resto: winter (nov-apr) ha rendimenti ~4.2% sopra summer su 323 anni e 89 paesi",
            perche="vacanze, flussi di compenso e risk appetite stagionali (Bouman-Jacobsen 2002); edge robusto globalmente MA noto da decenni → decay atteso alto",
            fonti=[f"{KB}/10-seasonal/README.md"],
            dati=["SPY EOD lake"],
            assets=["SPY, DAX proxy, SimFin equities"],
            timeframe=["1D, regime stagionale"],
            decay=40.0,
            effect="+4.2% winter vs summer (Bouman-Jacobsen 2002, pre-decay)",
        ),
        _kb(
            nome="turn-of-month-effect",
            meccanismo="long SPY primi 4 giorni trading del mese (TOM) + ultimi 2: i rendimenti si concentrano lì (Hensel-Ziemba 1987)",
            perche="flussi stipendi/pensioni ricorrenti entrano a inizio mese; documentato ma crowded → decay alto",
            fonti=[f"{KB}/10-seasonal/README.md"],
            dati=["SPY EOD lake"],
            assets=["SPY"],
            timeframe=["1D calendar"],
            decay=45.0,
        ),
        _kb(
            nome="santa-claus-rally",
            meccanismo="long ultimi 5 giorni dicembre + primi 2 gennaio: S&P +1.3% medio dal 1950, 76% positivo",
            perche="liquidità ridotta + anticipation January effect; crowded → decay",
            fonti=[f"{KB}/10-seasonal/README.md"],
            dati=["SPY EOD lake"],
            assets=["SPY"],
            timeframe=["1D calendar"],
            decay=45.0,
            effect="+1.3% medio sul periodo, 76% positivo (dal 1950)",
        ),
    ],
    # ---------------------------------------------------------------- 11
    "11-onchain": [
        _kb(
            nome="mvrv-extreme-reversal",
            meccanismo="MVRV (market value / realized value) > 3.5 → de-risk BTC (top storico); < 1.0 → accumulate (bottom); long/flat con soglie pre-registrate",
            perche="MVRV misura il profitto medio detenuto: agli estremi la propensione a vendere (profit-taking) o la capitulation creano i turn di ciclo",
            fonti=[f"{KB}/11-onchain/README.md"],
            dati=["Btcscan/Etherscan free API (UTXO/realized cap)", "prezzo BTC lake"],
            assets=["BTC, ETH"],
            timeframe=["1D/1W"],
        ),
        _kb(
            nome="exchange-outflow-accumulation",
            meccanismo="outflow da exchange sostenuto (7d net outflow z-score alto) → rialzo nei mesi successivi; inflow sostenuto → de-risk",
            perche="prelievi verso self-custody = accumulo a lungo termine (diamond hands), depositi = intenzione di vendita",
            fonti=[f"{KB}/11-onchain/README.md"],
            dati=["Etherscan/chain API exchange flows (free)", "prezzo lake"],
            assets=["BTC, ETH"],
            timeframe=["1D"],
        ),
        _kb(
            nome="sopr-regime",
            meccanismo="SOPR < 1 (vendite in perdita) in fase di discesa = capitulation → long; SOPR > 1 e in crescita durante il rally = sano",
            perche="la percentuale di output spesi in perdita identifica capitulation bottoms (sentiment on-chain verificabile, non dichiarativo)",
            fonti=[f"{KB}/11-onchain/README.md"],
            dati=["Btcscan API (free) o Binance Vision aggTrades proxy"],
            assets=["BTC"],
            timeframe=["1D"],
        ),
    ],
    # ---------------------------------------------------------------- 12
    "12-behavioral": [
        _kb(
            nome="de-bondt-thaler-long-reversal",
            meccanismo="long i 35 loser 3-5y (decile più svalutato), short i winner: i loser outperformano 3-5y dopo (asimmetrico, più forte a gennaio)",
            perche="overreaction: il mercato estrapola troppo i risultati passati e la correzione successiva genera il reversal (De Bondt-Thaler 1985)",
            fonti=[f"{KB}/12-behavioral/README.md"],
            dati=["SimFin/yfinance prezzi EOD (need 5y history)", "SimFin fundamentals"],
            assets=["US equities SimFin"],
            timeframe=["1Y formation → 1-3Y holding"],
        ),
        _kb(
            nome="dhs-overconfidence-underreaction",
            meccanismo="dopo run di risultati positivi (management overconfident) gli earnings beat si allungano in drift più persistente: long i ticker con momentum fondamentale + beat consecutivi",
            perche="overconfidence + biased self-attribution rallenta l'aggiustamento dei prezzi (Daniel-Hirshleifer-Subrahmanyam 1998, BL-KB-105)",
            fonti=[f"{KB}/12-behavioral/README.md", f"{KB}/AUDIT-2026-08-17.md"],
            dati=["SimFin earnings + prices", "SEC EDGAR filing dates"],
            assets=["US equities SimFin"],
            timeframe=["1Q"],
        ),
        _kb(
            nome="52-week-high-anchoring",
            meccanismo="prossimità al 52-week high (George-Hwang 2004): i titoli vicini al massimo annuale continuano a outperformare (anchoring bias: il massimo è visto come troppo caro)",
            perche="gli investitori ancorano al massimo storico recente e vendono troppo presto; l'aggiustamento avviene con drift",
            fonti=[f"{KB}/01-fundamental/README.md", f"{KB}/12-behavioral/README.md"],
            dati=["prezzi EOD SimFin/yfinance"],
            assets=["US equities SimFin"],
            timeframe=["1M"],
        ),
    ],
    # ---------------------------------------------------------------- 13
    "13-meta-synthesis": [
        _kb(
            nome="meta-labeling-sizing",
            meccanismo="modello secondario (LightGBM) impara quando fidarsi del segnale primario: features = regime + volatilità + confidenza segnale → output = sizing; solo trade con meta-prob > soglia",
            perche="separa la predizione (recall) dal sizing (precision): migliora Sharpe senza inventare segnali nuovi (López de Prado 2018)",
            fonti=[f"{KB}/13-meta-synthesis/README.md"],
            dati=["segnali candidati factory + features regime (lake)"],
            assets=["per candidato factory"],
            timeframe=["per segnale"],
        ),
        _kb(
            nome="hrp-portfolio-allocation",
            meccanismo="allocazione Hierarchical Risk Parity (clustering gerarchico sulle correlazioni) per il portafoglio dei candidati APPROVED: robusta OOS, senza inversione di matrice né stima rendimenti attesi",
            perche="le stime di rendimenti attesi sono fragili; HRP sfrutta solo la struttura di correlazione, più stabile (López de Prado 2016)",
            fonti=[f"{KB}/13-meta-synthesis/README.md"],
            dati=["equity curve candidati (runner BL-615)"],
            assets=["portafoglio factory"],
            timeframe=["1M rebalance"],
        ),
        _kb(
            nome="crowded-strategy-detection",
            meccanismo="metrica crowding (correlazione incrociata tra lanes candidate + decay IC rolling) sopra soglia → cap sizing delle strategie correlate (López de Prado 2019, BL-KB-109)",
            perche="strategie affollate condividono il rischio di liquidazione: la correlazione esplode nei drawdown e l'ensemble sembra diversificato finché non serve",
            fonti=[f"{KB}/13-meta-synthesis/README.md", f"{KB}/AUDIT-2026-08-17.md"],
            dati=["equity curve candidati", "rolling IC (modulo I-E esistente)"],
            assets=["ensemble factory"],
            timeframe=["1M"],
        ),
    ],
    # ---------------------------------------------------------------- crypto (MoonDev)
    "crypto-microstructure": [
        _md(
            nome="funding-extremum-reversal",
            meccanismo="funding rate 8h estremo (z-score rolling 60d o soglia annualizzata ≤ −20% / ≥ +25%) segnala posizioni long/short affollate e costose da tenere → reversal atteso",
            perche="il costo del carry spinge i marginal trader fuori dalla posizione affollata; il squeeze del funding estremo coincide con l'esaurimento del flusso direzionale (D1)",
            fonti=[f"{MD}/RISPOSTE_D1-D15.md"],
            dati=[
                "Binance Vision fundingRate zip 2020→ ($0, no key)",
                "OHLCV 1h lake (ffill + shift(1) dal settlement)",
            ],
            assets=["BTCUSDT, ETHUSDT, SOLUSDT"],
            timeframe=["1h, 4h"],
            decay=40.0,
            dati_posseduti=True,
        ),
        _md(
            nome="liquidation-cascade-reversal",
            meccanismo="volume liquidato orario > 10× mediana 30d (liq_volume_z estremo) → overshoot da vendite forzate → mean reversion nelle ore successive (event study pre/post)",
            perche="le liquidazioni forzate attraversano il book oltre il fair value (price impact classico); quando la pressione finisce il prezzo torna (D4; letteratura: fat tails BTC EJF 2022)",
            fonti=[f"{MD}/RISPOSTE_D1-D15.md"],
            dati=["Binance Vision liquidationSnapshot 2020→ ($0)", "OHLCV 1h lake"],
            assets=["BTCUSDT, ETHUSDT"],
            timeframe=["1h event windows"],
            decay=40.0,
            dati_posseduti=True,
        ),
        _md(
            nome="bb-squeeze-release",
            meccanismo="BB dentro Keltner (squeeze ON) → transizione release + ADX>25 + rottura banda BB = entrata nella direzione della rottura (parametri MoonDev fissati a priori: BB20/2.0, KC20/1.5, ADX14>25)",
            perche="la compressione di volatilità accumina ordini stop da entrambi i lati; il rilascio libera il movimento direzionale (D2; squeeze = compressione NON direzione: da solo IC≈0 atteso, il valore è nella combinazione)",
            fonti=[f"{MD}/RISPOSTE_D1-D15.md"],
            dati=["OHLCV 1h lake (già posseduti, zero dati nuovi)"],
            assets=["BTCUSDT, ETHUSDT, SOLUSDT"],
            timeframe=["1h"],
            decay=40.0,
            dati_posseduti=True,
        ),
        _md(
            nome="cvd-divergence",
            meccanismo="prezzo new high/low + CVD (cumulative delta da tick rule su aggTrades) non conferma → esaurimento aggressione → reversal; convergenza conferma il trend",
            perche="movimenti senza aggressione unilaterale sottostante sono short-covering/limit pull: privi di combustibile revertano (D5; proxy da OHLCV hanno correlazione bassa — serve il tick vero)",
            fonti=[f"{MD}/RISPOSTE_D1-D15.md"],
            dati=["Binance Vision aggTrades (~1-2.5 GB/anno, $0)", "OHLCV 1h lake"],
            assets=["BTCUSDT"],
            timeframe=["1h"],
            decay=45.0,
            dati_posseduti=True,
        ),
        _md(
            nome="session-seasonality",
            meccanismo="hour-of-day (UTC) + day-of-week come feature condizionanti su BTC 24/7: open US (14:30 UTC) e sovrapposizione EU/US come finestre ad attività/volatilità anormale",
            perche="la struttura dei partecipanti cambia nell'arco della giornata (EU istituzionale, US retail); effetti orari documentati ma deboli e attenuati post-2018 (D6: prior bassa, feature di contesto mai edge standalone)",
            fonti=[f"{MD}/RISPOSTE_D1-D15.md"],
            dati=["OHLCV 1h lake (già posseduti)"],
            assets=["BTCUSDT"],
            timeframe=["1h"],
            decay=45.0,
            dati_posseduti=True,
        ),
        _md(
            nome="funding-z-ml-feature",
            meccanismo="funding_z = z-score rolling 60d del funding 8h come feature continua scale-free (invece della soglia secca) per modelli ML e per condizioni di entry su altri fattori",
            perche="lo z-score normalizza il crowding attraverso i regimi di volatilità del funding (D1.4 raccomandazione esplicita)",
            fonti=[f"{MD}/RISPOSTE_D1-D15.md"],
            dati=["Binance Vision fundingRate", "OHLCV 1h lake"],
            assets=["BTCUSDT, ETHUSDT"],
            timeframe=["1h"],
            decay=40.0,
            dati_posseduti=True,
        ),
        _md(
            nome="perp-basis-carry",
            meccanismo="basis perp-spot estremo (annualizzato) → il costo del carry attira gli arbitraggisti e comprime il basis: fade del basis con hedge spot",
            perche="il basis riflette domanda leveraged unilaterale; agli estremi è paga-to-trade contro gli over-leveraged (D1.5: secondo fattore, rimandato)",
            fonti=[f"{MD}/RISPOSTE_D1-D15.md"],
            dati=["OHLCV perp + spot Binance Vision ($0)"],
            assets=["BTCUSDT, ETHUSDT"],
            timeframe=["1h, 1d"],
            decay=40.0,
            dati_posseduti=True,
        ),
    ],
}


def main() -> None:
    total = 0
    for domain, hyps in DOMAINS.items():
        reg = DomainRegistry(domain=domain)
        for h in hyps:
            h.id = reg.next_id()
            reg.add(h)
        save_registry(REGISTRY_DIR / f"{domain}.yaml", reg)
        total += len(hyps)
        print(f"{domain}: {len(hyps)} hypotheses")
    print(f"TOTAL: {total}")


if __name__ == "__main__":
    main()
