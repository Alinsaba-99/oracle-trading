"""BL-201 — Edge Portfolio v2: ensemble multi-segnale con hysteresys.

Composizione di 3 strategie "edge positive" identificate nel BL-200
edge-portfolio probe (`docs/reports/edge-portfolio/edge-portfolio.md`):

1. **roc_momentum_12** (mc=41%, DD=3.47%) — momentum sui rendimenti passati
2. **bollinger_20_2** (mc=35.5%, DD=4.53%) — mean reversion Bollinger
3. **donchian_breakout_10** (mc=32%, DD=3.57%) — breakout canale Donchian

Pattern d'integrazione (BL-201):
- Calcola i 3 segnali individuali per ogni barra
- Applica hysteresys (cambio stato solo se confidenza > soglia + persistenza N barre)
- Combina i 3 segnali con pesi statici (50/30/20 inizialmente, bilanciati per mc)
- Risultato: segnale ensemble per giorno futuro, valido per mc_pass_rate > 0.45
  su 200 simulazioni Monte Carlo e DD < 3% con MES sizing.

Verdetto attuale (sintesi interna 2026-08-15): il BL-200 probe ha identificato
queste 3 strategie come "above baseline" (mc_pass > RSI mean-rev baseline
27.7%), MA senza validazione anti-overfit (DSR/PBO/CPCV, ADR-017). Questo
modulo costruisce l'ensemble; la validazione onesta è il passo successivo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from analytics.backtest.protocol import BacktestSignal
from analytics.strategy.signals import BbandReversion, DonchianBreakout, RocMomentum


@dataclass(frozen=True)
class EdgeEnsembleV2Config:
    """Configurazione per l'ensemble multi-segnale v2.

    Attributes
    ----------
    roc_period : int
        Periodo per RocMomentum (default 12, dal BL-200 probe).
    bollinger_period : int
        Periodo Bollinger Bands (default 20).
    bollinger_std : float
        Numero di deviazioni standard per Bollinger (default 2.0).
    donchian_period : int
        Periodo per Donchian breakout (default 10, dal BL-200 probe).
    weight_roc : float
        Peso di roc_momentum nell'ensemble (default 0.50 — mc più alta).
    weight_bollinger : float
        Peso di bollinger (default 0.30 — mc media).
    weight_donchian : float
        Peso di donchian (default 0.20 — mc più bassa).
    hysteresis_bars : int
        Numero di barre di persistenza richiesta per cambio stato
        (default 2). Evita whipsaw su barre isolate.
    hysteresis_threshold : float
        Soglia di confidenza sopra la quale il cambio stato è permesso
        (default 0.60 = 60% dei 3 segnali concordano).
    """

    roc_period: int = 12
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    donchian_period: int = 10
    weight_roc: float = 0.50
    weight_bollinger: float = 0.30
    weight_donchian: float = 0.20
    hysteresis_bars: int = 2
    hysteresis_threshold: float = 0.60


class EdgeEnsembleV2:
    """Ensemble multi-segnale v2 con hysteresys per il BL-200 edge portfolio.

    Combina 3 strategie (RocMomentum, BollingerReversion, DonchianBreakout)
    con pesi statici + hysteresys su cambio stato. Risultato: segnale
    {-1, 0, +1} per barra, con minor whipsaw rispetto ai segnali individuali.
    """

    def __init__(self, config: EdgeEnsembleV2Config | None = None) -> None:
        self.config = config or EdgeEnsembleV2Config()
        # Validate weights sum
        total = self.config.weight_roc + self.config.weight_bollinger + self.config.weight_donchian
        if total <= 0:
            raise ValueError(f"weights sum {total} must be > 0")
        # Normalise
        self._w_roc = self.config.weight_roc / total
        self._w_boll = self.config.weight_bollinger / total
        self._w_don = self.config.weight_donchian / total

        # Build the 3 underlying specialists (long-flat = 0/1 for now)
        self._roc = RocMomentum(period=self.config.roc_period)
        self._boll = BbandReversion(
            period=self.config.bollinger_period, std=self.config.bollinger_std
        )
        self._don = DonchianBreakout(period=self.config.donchian_period)

    def compute_individual(self, data: pl.DataFrame) -> dict[str, np.ndarray]:
        """Compute the 3 individual specialist signals.

        Returns
        -------
        dict[str, np.ndarray]
            Keys: 'roc', 'bollinger', 'donchian'; values: Int8 arrays {-1, 0, 1}.
        """
        return {
            "roc": self._roc.compute(data).to_numpy().astype(np.int8),
            "bollinger": self._boll.compute(data).to_numpy().astype(np.int8),
            "donchian": self._don.compute(data).to_numpy().astype(np.int8),
        }

    def compute_weighted_score(self, data: pl.DataFrame) -> np.ndarray:
        """Compute the weighted ensemble score (continuous, before hysteresis).

        Returns
        -------
        np.ndarray
            Float array of weighted scores in roughly [-1, +1].
        """
        signals = self.compute_individual(data)
        # Convert each signal to {-1, 0, +1} (donchian/roc are long-flat 0/1; need shift)
        # Per BL-200: roc_momentum is long-flat (0/1); bollinger is long-flat (0/1);
        # donchian is long-flat (0/1). Convert to signed (long = +1, flat = 0).
        roc_signed = signals["roc"].astype(np.float64)
        boll_signed = signals["bollinger"].astype(np.float64)
        don_signed = signals["donchian"].astype(np.float64)

        weighted = self._w_roc * roc_signed + self._w_boll * boll_signed + self._w_don * don_signed
        return weighted

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute the hysteresis-gated ensemble signal.

        Returns
        -------
        pl.Series
            Int8 signal {-1, 0, +1} with hysteresis applied.
        """
        score = self.compute_weighted_score(data)
        # Hysteresis: a bar goes long only if score >= hysteresis_threshold
        # for at least hysteresis_bars consecutive bars. Exit when score
        # drops below 0.5 (no longer a strong signal).
        n = len(score)
        sig = np.zeros(n, dtype=np.int8)
        pos = 0  # current position state: 0 = flat, 1 = long
        bull_count = 0  # consecutive bars above threshold

        threshold_enter = self.config.hysteresis_threshold
        threshold_exit = 0.5  # exit when signal weakens below this
        hysteresis_bars = self.config.hysteresis_bars

        for i in range(n):
            s = score[i]
            if not np.isfinite(s):
                bull_count = 0
                continue
            if pos == 0:
                if s >= threshold_enter:
                    bull_count += 1
                    if bull_count >= hysteresis_bars:
                        pos = 1
                else:
                    bull_count = 0
            else:  # pos == 1
                if s < threshold_exit:
                    pos = 0
                    bull_count = 0
            sig[i] = pos
        return pl.Series("signal", sig, dtype=pl.Int8)


class _EdgeEnsembleV2Adapter(BacktestSignal):
    """Adapter to expose EdgeEnsembleV2 as a BacktestSignal (for pipeline plug-in)."""

    def __init__(self, config: EdgeEnsembleV2Config | None = None) -> None:
        self._impl = EdgeEnsembleV2(config=config)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return self._impl.compute(data)


def build_edge_ensemble_v2(
    *,
    roc_period: int = 12,
    bollinger_period: int = 20,
    bollinger_std: float = 2.0,
    donchian_period: int = 10,
    weight_roc: float = 0.50,
    weight_bollinger: float = 0.30,
    weight_donchian: float = 0.20,
    hysteresis_bars: int = 2,
    hysteresis_threshold: float = 0.60,
) -> EdgeEnsembleV2:
    """Factory: build EdgeEnsembleV2 with explicit kwargs (no dataclass)."""
    return EdgeEnsembleV2(
        EdgeEnsembleV2Config(
            roc_period=roc_period,
            bollinger_period=bollinger_period,
            bollinger_std=bollinger_std,
            donchian_period=donchian_period,
            weight_roc=weight_roc,
            weight_bollinger=weight_bollinger,
            weight_donchian=weight_donchian,
            hysteresis_bars=hysteresis_bars,
            hysteresis_threshold=hysteresis_threshold,
        )
    )


__all__: list[str] = ["EdgeEnsembleV2", "EdgeEnsembleV2Config", "build_edge_ensemble_v2"]
