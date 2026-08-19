# 09 Cyclical — Data Audit (free $0 verified 2026-08-17)

> Regola hard: $0/mo per dati. Vedi ADR-020.

## Fonti cyclical analysis free

| Fonte | Coverage | Format | API Key | Note |
|---|---|---|---|---|
| **yfinance historical price** | 1990+ daily for most assets | pandas DataFrame | nessuna | For Hurst exponent + cycle detection |
| **Dukascopy lake** | 2003+ 1m+1h+1d | parquet cached | nessuna | Higher resolution for intraday cyclical |
| **statsmodels (Python lib)** | Hurst exponent + FFT | Python lib | nessuna | `from statsmodels.tsa.stattools import hurst_exp` |
| **numpy + scipy FFT** | spectral analysis | Python lib | nessuna | `from scipy.fft import fft, fftfreq` |
| **hurster (Python lib)** | advanced Hurst methods | Python lib | nessuna | `pip install hurst`. R/S + DMA + wavelet methods |
| **SchrödingerWavelets** | wavelet analysis | Python lib | nessuna | For cycle decomposition |

## Capabilities Oracle esistenti

- ✅ Dukascopy lake 21 symbols cached
- ✅ NautilusTrader + vectorbt (for backtest)
- ✅ statsmodels installed (HP filter from dominio 02)
- ✅ scikit-learn (for FFT spectral analysis)

## Gap dichiarati

1. **Hurst exponent calculator** NON implementato. TODO BL-KB-69.
2. **Cycle detector (FFT)** NON implementato. TODO BL-KB-70.
3. **Schumpeter 4-tier cycle classifier** NON implementato. TODO BL-KB-71 (long-horizon macro overlay).

## Cap da NON usare

| Fonte | Perché esclusa | Alternativa free |
|---|---|---|
| Elliott Wave proprietary platforms | mysticism + subjective | Hurst + FFT objective |
| Gann proprietary calculators | subjective | Hurst + cycle FFT |
| Bloomberg cycle analysis | $24k/yr | yfinance + statsmodels |

## Reference implementations free

- **hurster Python**: https://github.com/Mottl/hurst — R/S analysis
- **statsmodels Hurst**: https://www.statsmodels.org/stable/index.html
- **scipy FFT**: https://docs.scipy.org/doc/scipy/reference/fft.html
- **Wavelet analysis**: pywavelets `pip install pywt`
