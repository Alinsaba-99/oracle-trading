"""Build the canonical data/macro/economic_calendar.json fixture (BL-724)."""

from pathlib import Path

from market.calendar import build_and_persist_default_calendar


def main() -> None:
    target = Path("data/macro/economic_calendar.json")
    cal = build_and_persist_default_calendar(target)
    print(f"Wrote {len(cal)} events to {target}")


if __name__ == "__main__":
    main()
