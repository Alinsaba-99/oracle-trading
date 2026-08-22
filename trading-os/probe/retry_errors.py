"""Retry the API_ERROR rows in metadata.tsv in place."""

from __future__ import annotations

from pathlib import Path

from fetch_metadata import _token, fetch

HERE = Path(__file__).resolve().parent


def main() -> None:
    path = HERE / "metadata.tsv"
    rows = [line.split("\t") for line in path.read_text().splitlines() if line]
    token = _token()
    fixed = 0
    for i, row in enumerate(rows):
        if len(row) >= 2 and row[1] == "API_ERROR" and row[0] != "huggingface/":
            try:
                rows[i] = list(fetch(row[0], token))
                fixed += 1
                print("fixed", row[0])
            except Exception as exc:
                print("still-error", row[0], type(exc).__name__, exc)
    path.write_text("\n".join("\t".join(r) for r in rows) + "\n")
    print(f"fixed {fixed} rows")


if __name__ == "__main__":
    main()
