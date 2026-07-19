# Crew Workers — Project Mapping Tools

Worker specializzati per analizzare diverse dimensioni del progetto Oracle.
Ogni worker è uno script Python indipendente che produce output strutturato.

## Worker disponibili

| Worker | Funzione |
|---|---|
| `crew-pkgmap` | Mappa la struttura package Python: init exports, file count, moduli |
| `crew-depmap` | Analizza il grafo delle import tra package (trova violazioni clean arch) |
| `crew-contracts` | Trova tutti i contract Pydantic/dataclass/typing nel codebase |
| `crew-untracked` | Analizza i file untracked/new: struttura e contenuto |
| `crew-safety` | Mappa il safety control plane: risk, OMS, ledger, execution paths |
| `crew-gates` | Verifica evidenza gate dal codice (G0-G9) |
| `crew-tests` | Mappa struttura test, coverage gaps, categorie |

## Utilizzo

```bash
# Tutti i worker
cd /home/alin/_repos/oracle-trading
python scripts/crew/crew-pkgmap
python scripts/crew/crew-depmap
python scripts/crew/crew-contracts
python scripts/crew/crew-untracked
python scripts/crew/crew-safety
python scripts/crew/crew-gates
python scripts/crew/crew-tests

# Worker specifico con filtro
python scripts/crew/crew-depmap --package agents
python scripts/crew/crew-contracts --domain-only
python scripts/crew/crew-untracked --summary
python scripts/crew/crew-safety --bypass
```
