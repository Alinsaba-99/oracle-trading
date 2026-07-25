# ADR-014 — Loss of M31 replay/regime evidence (audit-remediation-beta)

> Status: Accepted
> Date: 2026-07-23
> Supersedes: nothing
> Author: lead-agent on audit-remediation-beta

## Context

During audit-remediation-beta (commit `974ab91` and ancestors), the
following drift was found (audit report B4):

1. **The module `analytics/qualification/regime.py` does not exist.**
   It is referenced in some planning documents under the name
   "regime selector", but no such module is present in the codebase
   nor in `git log` history, nor in any of the abandoned worktree
   snapshots under `.omx/team/restore-the-oracle-tr-*/worktrees/`.
2. **The dataset `data/ohlcv/ES_1d.parquet` has a different SHA-256
   than the one recorded for the M31 qualification evidence.**
   Recorded M31 hash: `09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42`
   Current hash:        `9a526125a75c412434faff09810a683528548df31ed915d2a895caf3b1216dfb`

These two facts together invalidate any prior claim that "M31 evidence
is reproducible" — i.e. G5 (Research Truth) is REGRESSED, and the path
back to "G5 PASSED" is not "restore missing files".  The regime module
never existed; the dataset was re-generated out-of-band and the
original qualifying row set is lost.

## Decision

1. **G5 is declared NOT_STARTED until M31 is re-run end-to-end.** The
   prior "APPROVED" status of M31 is considered cancelled because the
   evidence artifact is no longer reproducible.
2. **No time is spent on git-archaeology to recover `regime.py`.**
   Investigation confirmed the file was never committed; the planning
   documents referenced an aspirational module name that was never
   implemented.
3. **`analytics/qualification/models.ReplayRegime` is the canonical
   regime taxonomy** today (4 regimes, see enum).  Any new regime
   classification must be implemented in this module, not as a new
   file.
4. **M31 will be re-run as part of a new work package after audit-
   remediation-beta lands.**  Target: 1 sprint of focused work to
   regenerate evidence with the post-beta fixes (OMS VWAP, ledger
   notional, idempotency persistence).
5. **The data hash story is recorded as "data lineage GAP".**  Future
   re-runs must commit the exact data hash in the report header so a
   regeneration event is auditable.

## Consequences

- The `ORACLE_AUTOPILOT_STATUS.md` gate table should mark G5 as
  NOT_STARTED (not REGRESSED — there's no evidence TO regress).
- The `ORACLE_AUTOPILOT_BACKLOG.md` should add a new entry "Re-run
  M31 with post-beta fixes" under a new gate follow-up.
- Any 20-year annual paper replay numbers (or 60-window rolling
  diagnostic numbers) computed against the current dataset should be
  treated as informational, not as M31 evidence.

## References

- `/tmp/audit-finale-oracle-trading.md` — finding B4
- `analytics/qualification/models.py:12-13` — `ReplayRegime` enum
- `data/ohlcv/ES_1d.parquet` — current dataset (hash in commit message
  of beta.1)
