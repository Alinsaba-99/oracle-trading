"""F0 Oracle Terminal — extract design references with Playwright.

Captures full-page screenshots and computed design tokens (palette,
typography, spacing) from public reference trading UIs.  Only textual
artifacts are committed: screenshots stay local (gitignored).

Usage: uv run python scripts/ui_extract_design_refs.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("docs/design-references/oracle-terminal")

TARGETS = {
    "binance-trade": {
        "url": "https://www.binance.com/en/trade/BTC_USDT?type=spot",
        "wait_ms": 12000,
        "note": "Spot trading page: order ticket, order book, market list",
    },
    "tradingview-symbol": {
        "url": "https://www.tradingview.com/symbols/BTCUSD/",
        "wait_ms": 10000,
        "note": "Public symbol page: chart, toolbar, panels",
    },
}

TOKEN_JS = """
() => {
  const sample = [...document.querySelectorAll('*')].slice(0, 4000);
  const bgs = {};
  const fgs = {};
  const fonts = {};
  const radii = [];
  for (const el of sample) {
    const cs = getComputedStyle(el);
    if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)') {
      bgs[cs.backgroundColor] = (bgs[cs.backgroundColor] || 0) + 1;
    }
    if (cs.color) fgs[cs.color] = (fgs[cs.color] || 0) + 1;
    const ff = cs.fontFamily.split(',')[0].trim().replace(/['"]/g, '');
    fonts[ff] = (fonts[ff] || 0) + 1;
    if (cs.borderRadius && cs.borderRadius !== '0px') radii.push(cs.borderRadius);
  }
  const top = (c, n) => Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, n)
    .map(([v, n]) => ({value: v, count: n}));
  const body = getComputedStyle(document.body);
  const h1 = document.querySelector('h1,h2');
  const btn = document.querySelector('button');
  const mono = ['body font', body.fontFamily];
  return {
    background_top: top(bgs, 14),
    foreground_top: top(fgs, 14),
    fonts_top: top(fonts, 8),
    border_radius_top: top(radii.reduce((a, r) => (a[r] = (a[r] || 0) + 1, a), {}), 8),
    body: {
      backgroundColor: body.backgroundColor,
      color: body.color,
      fontFamily: body.fontFamily,
      fontSize: body.fontSize,
      lineHeight: body.lineHeight,
    },
    heading: h1 ? {
      fontFamily: getComputedStyle(h1).fontFamily,
      fontSize: getComputedStyle(h1).fontSize,
      fontWeight: getComputedStyle(h1).fontWeight,
      letterSpacing: getComputedStyle(h1).letterSpacing,
    } : null,
    button: btn ? {
      backgroundColor: getComputedStyle(btn).backgroundColor,
      color: getComputedStyle(btn).color,
      borderRadius: getComputedStyle(btn).borderRadius,
      padding: getComputedStyle(btn).padding,
      fontFamily: getComputedStyle(btn).fontFamily,
    } : null,
    viewport: {w: innerWidth, h: innerHeight},
  };
}
"""


async def extract_one(browser, key: str, cfg: dict) -> dict:
    out_dir = OUT / key
    (out_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    result: dict = {"url": cfg["url"], "note": cfg["note"], "captures": []}
    for label, vp in (
        ("desktop", {"width": 1440, "height": 900}),
        ("mobile", {"width": 390, "height": 844}),
    ):
        ctx = await browser.new_context(
            viewport=vp,
            device_scale_factor=1,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await ctx.new_page()
        entry: dict = {"viewport": label}
        try:
            await page.goto(cfg["url"], wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(cfg["wait_ms"])
            shot = out_dir / "screenshots" / f"{label}-full.png"
            await page.screenshot(path=str(shot), full_page=True)
            entry["screenshot"] = str(shot)
            if label == "desktop":
                entry["tokens"] = await page.evaluate(TOKEN_JS)
            entry["title"] = await page.title()
            entry["ok"] = True
        except Exception as exc:
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"[:300]
        result["captures"].append(entry)
        await ctx.close()
    return result


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"]
        )
        report: dict = {}
        for key, cfg in TARGETS.items():
            print(f"extracting {key} ...", flush=True)
            report[key] = await extract_one(browser, key, cfg)
        await browser.close()
    (OUT / "tokens.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for key, data in report.items():
        for cap in data["captures"]:
            status = "ok" if cap.get("ok") else f"FAIL {cap.get('error', '')[:80]}"
            print(f"  {key}/{cap['viewport']}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
