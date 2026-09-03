# BL-726 — Pre-Registration: Lane B Composite Variant (Aggressive Profile)

> **BL**: BL-726 (P1, pre-registered decision (a) per
> `BACKLOG.md` "Note operative" priority chain).
> **Lane**: B (portafoglio personale operatore, ADR-019).
> **Variant**: `lane_b_composite_aggressive`.
> **Anti-HARKing anchor**: this document + the accompanying manifest
> (`BL-726.manifest.json`) are pinned BEFORE the qualification run
> (`BL-727`).  No parameter, threshold, or sample window may be edited
> after the run; the only acceptable post-result action is to declare
> the variant `REJECTED` and re-open BL-726 with a new manifest
> (`schema_version` bump).

---

## 1. Context

The Lane B composite strategy (`analytics/strategy/lane_b_backtester.py`)
was first characterised against SimFin 2020-01 → 2025-08 in
`docs/reports/lane-b-composite/2026-08-17-compare.md` (composite
Sharpe 0.93, alpha +59% vs SPY, Max DD 24.7%).  Its formal
qualification via the ADR-017 gauntlet (DSR/PBO/CPCV) was attempted in
`BL-OPC-12` (`docs/reports/lane-b-composite/2026-08-20-qualification.md`)
and **REJECTED** with PBO 0.635 and a bear-2022 Sharpe of 0.05.

The post-mortem conclusion recorded in `BACKLOG.md` §"Note operative":
the failure was driven by **researcher degrees of freedom** — the
qualification sweep compared five variants of the composite
(threshold 0.55 / 0.65 default / 0.70, weights 40/40/20 vs 50/30/20,
legacy AND) and an eight-trial ``n_trials`` DSR penalty, which left
plenty of room for the in-sample optimum to be overfit.  The bear-2022
failure additionally demonstrated the composite is **bull-market-only**
on the default 2020-08-15 parameter set.

The pre-registered cure (decision (a) of the priority chain): pick
**ONE** frozen variant with the BL-505d aggressive profile (per-idea
stop-loss 5%, vol target 40%), run the gauntlet against a SINGLE
returns matrix (no config family), and judge purely on the canonical
DSR / PSR / CPCV / haircut-Sharpe metrics.  No post-hoc variant
selection, no threshold tuning after the run.

This document is the public record of that pre-registration.

---

## 2. Frozen variant — parameter table

Every tunable the backtester accepts is listed below.  Anything not in
this table MUST take its `LaneBBacktestConfig` default at runtime — and
because the dataclass is frozen, those defaults are themselves
immutable (see `analytics/strategy/lane_b_backtester.py:75-89`).

| Parameter                         | Frozen value           | Lives in (file:line)                                                          |
|-----------------------------------|------------------------|-------------------------------------------------------------------------------|
| `initial_capital`                 | `100_000.0`            | `analytics/strategy/lane_b_backtester.py:75`                                  |
| `rebalance_months`                | `3` (quarterly)        | `analytics/strategy/lane_b_backtester.py:76`                                  |
| `top_n_holdings`                  | `15`                   | `analytics/strategy/lane_b_backtester.py:77`                                  |
| `min_f_score`                     | `8`                    | `analytics/strategy/lane_b_backtester.py:78`                                  |
| `magic_rank_max`                  | `50`                   | `analytics/strategy/lane_b_backtester.py:79`                                  |
| `return_12m_min`                  | `-0.10`                | `analytics/strategy/lane_b_backtester.py:80`                                  |
| `return_12m_max`                  | `0.50`                 | `analytics/strategy/lane_b_backtester.py:81`                                  |
| `benchmark_simfin_id`             | `1072401` (SPY ETF)    | `analytics/strategy/lane_b_backtester.py:82`                                  |
| `target_annual_vol`               | `0.40` (declared only) | `analytics/strategy/lane_b_backtester.py:83`                                  |
| `sector_blacklist`                | `()` (empty)           | `analytics/strategy/lane_b_backtester.py:84`                                  |
| `per_idea_stop_loss_pct`          | `0.05`                 | `analytics/strategy/lane_b_backtester.py:85`                                  |
| `use_composite`                   | `True`                 | `analytics/strategy/lane_b_backtester.py:86`                                  |
| `composite_weights`               | `(0.40, 0.40, 0.20)`   | `analytics/strategy/lane_b_backtester.py:87`                                  |
| `composite_threshold`             | `0.65`                 | `analytics/strategy/lane_b_backtester.py:88`                                  |
| `composite_return_band`           | `(-0.20, 0.50)`        | `analytics/strategy/lane_b_backtester.py:89`                                  |
| `CompositeLaneBScore.w_f_score`   | `0.40`                 | `analytics/strategy/catalog/value.py:436`                                     |
| `CompositeLaneBScore.w_magic_rank`| `0.40`                 | `analytics/strategy/catalog/value.py:437`                                     |
| `CompositeLaneBScore.w_return_12m`| `0.20`                 | `analytics/strategy/catalog/value.py:438`                                     |
| `CompositeLaneBScore.band_min`    | `-0.20`                | `analytics/strategy/catalog/value.py:439`                                     |
| `CompositeLaneBScore.band_max`    | `0.50`                 | `analytics/strategy/catalog/value.py:440`                                     |
| `CompositeLaneBScore.threshold`   | `0.65`                 | `analytics/strategy/catalog/value.py:441`                                     |
| Per-idea stop-loss application     | cumulative-return from first window day; once `cum_return ≤ -stop_loss_pct`, daily return is zeroed for the rest of the window | `analytics/strategy/lane_b_backtester.py:567-639` |

### 2.1 Known gap — `target_annual_vol=0.40` is declared, NOT applied

`LaneBBacktestConfig.target_annual_vol` is set to `0.40` in the
manifest, but **the backtester does not currently apply vol-target
position sizing** to the equal-weight returns computation
(`analytics/strategy/lane_b_backtester.py:435-443` and surrounding
code contains a TODO marker for BL-505e).  In other words the
qualification will run on the composite screen + per-idea stop-loss
+ equal-weight sizing; the "vol target 40%" leg is aspirational and
remains a pre-condition for live paper-promotion (BL-732), not for
qualification (BL-727).  This gap is declared openly so the future
runner cannot surprise anyone.

### 2.2 Universes screened

| Item                     | Value                                                   |
|--------------------------|---------------------------------------------------------|
| `SimFinLoader.market`    | `"US"`                                                  |
| `SimFinLoader.data_dir`  | `data/simfin`                                           |
| Income variant           | `quarterly`                                             |
| Price field               | daily `Close`, `Adj. Close`, `Volume`                   |
| Universe available       | 6,537 US companies; 49,020 income / 49,017 balance / 49,019 cash-flow quarterly statements; 6,225,717 daily prices (as of 2026-08-15 snapshot, ADR-019 §3) |
| Universe actually selected | `top_n_holdings = 15` after the composite screen       |
| Benchmark                | SPY ETF (`SimFinId = 1072401`)                          |

---

## 3. Data spec

### 3.1 Source

SimFin bulk (`analytics/fundamental/simfin_loader.py`, MIT-licensed
`simfin` package).  All statements and prices are fetched by the bulk
endpoints and cached under `data/simfin/`; the runner reads from that
cache, so the qualification is reproducible from a fixed snapshot.

### 3.2 Point-in-time discipline

- **PIT marker**: the `Publish Date` column of each statement
  (`analytics/strategy/lane_b_backtester.py:23-24` and `:185-189`).  The
  backtester filters on `publish_date ≤ as_of_date` and then takes the
  most recent per `SimFinId`, guaranteeing that no statement whose
  publish date is later than the screening date leaks into the
  features.  This is the SimFin-bulk-v1 PIT convention.
- **Restatements**: NOT handled in the current code.  The `Restated
  Date` column is ignored (`lane_b_backtester.py:23-24`).  This is a
  known PIT gap documented at BL-619 scope; flagged here so the
  qualification output is interpreted against that caveat.

### 3.3 Environment

- `SIMFIN_API_KEY` (env var, free tier; ADR-020 zero-cost).
- `data/simfin/` cache (git-ignored via BL-605).

### 3.4 Sample window (HONEST split)

| Subwindow                        | Range                       | Role                                                 |
|----------------------------------|-----------------------------|------------------------------------------------------|
| **Qualification (full)**         | `2020-01-01 → 2025-08-14`   | Full backtest producing the observed Sharpe / DD / alpha |
| **Train** (in-sample for any future retrain) | `2020-01-01 → 2023-12-31` | Honest reference for IS-only refits; here it is informational only since the variant has no fitted parameters |
| **Validation (OOS)**             | `2024-01-01 → 2025-08-14`   | OOS reporting region for the headline numbers; pinned here so re-runs cannot silently shift it |
| **Bear 2022 (sub-experiment)**   | `2022-01-01 → 2022-12-31`   | Secondary gate; see §6 |

Justification of the train/validation split: the CPCV machinery
(`analytics/qualification/dsr.py::combinatorial_purged_cv` with
`n_groups=6, n_test_groups=2`) honours chronological order via
`purgedcv`'s `CombinatorialPurgedCV`, so the validation 2024+ region
is a clearly identified out-of-sample window.  Anchoring an explicit
`train_subwindow` / `validation_subwindow` makes the split auditable
even before any future refit of the screen.  Pinned before the run.

---

## 4. Qualification protocol (ADR-017 gauntlet)

The variant must pass all of:

| Step | Metric / tool                                   | Threshold                                       | Module                                                                    |
|------|--------------------------------------------------|--------------------------------------------------|---------------------------------------------------------------------------|
| 4.1  | Observed Sharpe (canonical, ADR-021)            | informational (no fixed min)                     | `analytics/metrics/canonical.py::sharpe_ratio`                            |
| 4.2  | Deflated Sharpe Ratio (DSR)                       | `≥ 0.95` at 95% confidence                       | `analytics/qualification/dsr.py::deflated_sharpe_ratio`                    |
| 4.3  | Probabilistic Sharpe Ratio (PSR)                  | `≥ 0.95`                                         | `analytics/qualification/dsr.py::probabilistic_sharpe_ratio`              |
| 4.4  | Probability of Backtest Overfitting (PBO)         | `< 0.20` (single-row variant returns matrix → PBO `None`; see note) | `analytics/qualification/dsr.py::probability_of_backtest_overfitting`     |
| 4.5  | CPCV OOS Sharpe median                            | `> 0.50`                                         | `analytics/qualification/lane_b.py::cpcv_oos_sharpes`                     |
| 4.6  | Haircut Sharpe Ratio (BL-707, BL-KB-99)           | `> 0.50`                                          | `analytics/research/factory/haircut_sharpe.py::haircut_sharpe_ratio`     |
| 4.7  | Pre-registered IC screen (BL-706)                 | `ICIR > 0.05`, `block-bootstrap t > 2.5`, `ICIR × (1 − 30%)` retained, direction positive | `analytics/research/factory/ic_screen.py::screen_factor` |
| 4.8  | Bear-2022 Sharpe (secondary)                      | `> 0.0`                                           | computed on the 2022 slice of the full backtest                          |
| 4.9  | Canonical runner                                 | `apps/cli/paper_commands.py::run_paper_spec` (BL-615) — single code path, manifest written next to the result |

All thresholds were fixed BEFORE this pre-registration was written.
They are documented in §6 with literature provenance; they are
recorded in the manifest so the loader (`analytics/research/factory/prereg.py`)
can validate the file the qualification run is launched against.

> **Note on PBO**: with `n_trials = 1` and a single-variant returns
> matrix of shape `(1, n_periods)`, the CSCV machinery has no
> family to compare against and reports `pbo = None`.  The
> overfitting protection therefore comes from the CPCV OOS median
> + DSR (`n_trials = 1` collapses the multiple-testing correction to
> the PSR) + haircut Sharpe.  The `pbo_max` field is kept in the
> manifest for the day a multi-variant comparison is reintroduced
> (then it re-tightens to `< 0.20` instead of the ADR-017 default
> `< 0.5`, justified by the BL-OPC-12 finding of `PBO 0.635`).

---

## 5. Code under qualification

```
commit 6e3f8a0456d0ce38cd6a881a36976f62fd8bd97f (HEAD -> feat/p1-metrics-truth, origin/main)
Author: Alin <redacted>
Date:   2026-08-22

    docs(status): sessione 2026-08-22 — BL-711/701/702/706/707/721 eseguiti, suite 3089 passed
```

> **Working-tree clause (must hold at qualification time)**: the
> working tree MUST be clean in every qualification-affecting path
> listed below, and `git rev-parse HEAD` MUST equal
> `6e3f8a0456d0ce38cd6a881a36976f62fd8bd97f`.  The loader
> (`analytics/research/factory/prereg.py::verify_clean_tree`) enforces
> both conditions at run start; a violation aborts the run before any
> metric is computed.
>
> Qualification-affecting paths (whitelist, exact prefixes):
>
> - `analytics/strategy/`
> - `analytics/research/`
> - `analytics/qualification/`
> - `analytics/metrics/`
> - `analytics/fundamental/simfin_loader.py`
>
> Untracked files outside these prefixes (docs/, scripts/, etc.) do
> NOT trip the verifier; modifications inside them DO (because tracked
> changes anywhere in the repo move HEAD off the pinned commit).

> **Note on the as-of state of this pre-registration**: at the
> moment this document was authored, the working tree was NOT clean
> (BACKLOG.md had uncommitted additions, plus untracked files in
> `docs/design-references/`, `docs/plans/`, `scripts/`,
> `tests/unit/test_alerting_*`, etc.).  NONE of those modifications
> touches a whitelist path, so `verify_clean_tree` would pass if run
> right now.  Before launching BL-727 the operator MUST re-run
> `git status --porcelain` and ensure no whitelist diffs have
> accumulated.

`git diff --stat` at the time of authoring:

```
 BACKLOG.md | 72 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 72 insertions(+)
```

(Outside the whitelist — does not invalidate the manifest.)

---

## 6. Pre-registered thresholds — justification

Each threshold below was chosen by literature reference, NOT by
tuning to the qualification output (which does not exist at the time
this document is signed).

| Threshold                  | Value   | Justification                                                                                                                                                                                                                                                                                                                                                                |
|----------------------------|---------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `dsr_min`                  | `0.95`  | ADR-017 (BL-500), Bailey & López de Prado 2014 §3: DSR ≥ 0.95 is the standard "edge survives the multiple-testing penalty" bar for a single best-of-N trial.  This pre-registration sets `n_trials = 1` because the variant is single (no config family), so DSR degenerates to the PSR; the bar is therefore "true Sharpe > 0 at 95% confidence under the conservative penalty". |
| `psr_min`                  | `0.95`  | ADR-017, Bailey & López de Prado 2012: PSR ≥ 0.95 means ≥ 95% probability the true Sharpe exceeds the benchmark (here, `0.0`).  Same provenance as `dsr_min`; both must hold for the variant to claim any edge.                                                                                                                                                                |
| `pbo_max`                  | `0.20`  | Tighter than the ADR-017 default of `0.5` because BL-OPC-12 measured `PBO = 0.635` on the family that included the composite at multiple thresholds / weights; a stricter bar is needed to actually close the overfitting hole.  When the variant is run with `n_trials = 1` (single-row returns matrix) PBO is `None` and the threshold is reported as "not applicable" in the verdict. |
| `cpcv_oos_sharpe_median_min` | `0.50` | ADR-019 §2: "Sharpe target ≥ 0.5 su paniere 20-30 titoli turnaround simultanei" is the Lane B personal-portfolio deployment threshold; applying it to the CPCV OOS median (honest out-of-sample) is the strictest interpretation of that target.                                                                                                                                   |
| `haircut_sharpe_min`       | `0.50`  | BL-707 / BL-KB-99 (Bailey-López de Prado 2018): the haircut adjusts the observed Sharpe for skew/kurtosis and multiple-testing.  `haircut_SR > 0.5` is the conservative analog of "Lane B Sharpe ≥ 0.5 after the honesty haircut" — anything below is a noise-flavoured bet.                                                                                                  |
| `icir_threshold`           | `0.05`  | BL-706 design spec (`docs/plans/2026-08-21-edge-research-factory-design.md` §6).  Pinned before the run; the IC screen has no post-hoc adjustment.                                                                                                                                                                                                                          |
| `icir_haircut_pct`         | `30.0`  | BL-706 design spec, post-publication decay assumption (per `BL-KB-99` study).                                                                                                                                                                                                                                                                                                |
| `ic_block_t_threshold`     | `2.5`   | BL-706 design spec; standard "t > 2" bar with a half-unit buffer for non-normality in the bootstrap.                                                                                                                                                                                                                                                                          |
| `bear_2022_sharpe_min`     | `0.0`   | BL-OPC-12 measured `Sharpe 0.05` on the composite default during the 2022 bear; anything ≤ 0 means the variant is net-destructive in a real bear regime.  Full DSR/PBO machinery is NOT applied to the bear slice (252 trading days is borderline for the statistical tools).                                                                                                |

---

## 7. Anti-HARKing clause

- Every threshold in §6 was fixed BEFORE this document was written;
  the qualification run (`BL-727`) has not yet been executed.
- The accompanying manifest (`docs/research/prereg/BL-726.manifest.json`,
  sha256 = `21fddc7b89a8877400e469a6d7bc5fa31a4154d4f14cb1a38d0e9af94c065e32`)
  pins all parameters and thresholds in machine-checkable form.
- Any modification of the manifest or this document AFTER the
  qualification run is FORBIDDEN.  The only acceptable post-result
  action is to declare the variant `REJECTED` in the
  `BL-727` runner output and re-open BL-726 with a new
  `schema_version` bump (`schema_version: 2`, new thresholds, new
  parameters, new code commit).  The downstream BL-732 (paper
  promotion) MUST consume the manifest that matches the run; any
  drift trips `verify_clean_tree` and the loader refuses to start.
- HARKing incident-class: a researcher changing the threshold
  retroactively to make a borderline variant pass is treated as a
  P1 governance violation and triggers the BL-014 audit trail.

---

## 8. Manifest integrity

The accompanying JSON manifest is the machine-checkable contract.

| File                                                    | sha256                                                          |
|---------------------------------------------------------|-----------------------------------------------------------------|
| `docs/research/prereg/BL-726.manifest.json`             | `21fddc7b89a8877400e469a6d7bc5fa31a4154d4f14cb1a38d0e9af94c065e32` |

> Re-hash the manifest with `python -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' docs/research/prereg/BL-726.manifest.json`
> if the file is ever edited (it should not be — see §7).

The manifest is consumed by `analytics/research/factory/prereg.py`:

- `load_prereg(path)` deserialises and validates the schema.
- `verify_clean_tree(expected_commit, repo_root)` asserts HEAD matches
  and the working tree is clean in the qualification-affecting paths.

Both are exercised by `tests/unit/test_prereg.py` (round-trip,
threshold parsing, dirty-tree detection, dirty HEAD detection).

---

## 9. References

- `BACKLOG.md` §"Note operative" — pre-registered decision (a).
- `BACKLOG.md` §"P1 — Verità metrica e runner canonico (BL-610..619)".
- `docs/ADR/ADR-017-backtest-overfitting-validation-upgrade.md`.
- `docs/ADR/ADR-019-lane-b-priority-personal-portfolio.md`.
- `docs/ADR/ADR-021-canonical-performance-metrics.md`.
- `docs/plans/2026-08-21-edge-research-factory-design.md` §6 (IC
  screen criteria).
- `docs/reports/lane-b-composite/2026-08-17-compare.md`
  (composite characterisation).
- `docs/reports/lane-b-composite/2026-08-20-qualification.md`
  (BL-OPC-12 REJECTED verdict, PBO 0.635, bear Sharpe 0.05).
- `docs/reports/lane-b/BL-505d-aggressive-report.md` (the aggressive
  profile that this pre-registration freezes).
- Bailey & López de Prado (2012, 2014, 2018) — PSR / DSR / haircut SR.
- López de Prado (2018). *Advances in Financial Machine Learning*. ch.7-12.
