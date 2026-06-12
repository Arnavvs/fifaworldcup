"""
SofaScore WC2026 scraper.

Uses real Chrome via Playwright to bypass Cloudflare, intercepts API responses.
Requires: conda activate minorproject (Playwright env)

Usage:
    C:\\Users\\HP\\anaconda3\\envs\\minorproject\\python.exe scrapers/sofascore_test.py

What it captures:
    - Group standings (live, 12 groups x 4 teams)
    - Match schedule + results (32+ events)
    - Power rankings (48 teams)
    - Featured odds (where available)

Limitations (Cloudflare):
    - Match-level stats, lineups, incidents: BLOCKED via fetch()
    - Individual match odds: BLOCKED
    - Only captures what the tournament page loads naturally

After running, integrate into DB:
    python scrapers/sofascore_integrate.py

SofaScore IDs:
    Tournament: 16 (FIFA World Cup)
    Season: 58210 (2026)
"""
import asyncio
import json
import os

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sofascore_data")
os.makedirs(OUTDIR, exist_ok=True)

captured = {}

def save_json(name, data):
    fpath = os.path.join(OUTDIR, f"{name}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, channel="chrome",
            args=["--window-size=1200,800"]
        )
        ctx = await browser.new_context(viewport={"width": 1200, "height": 800})
        page = await ctx.new_page()

        async def on_response(response):
            url = response.url
            if "/api/v1/" in url and response.status == 200:
                try:
                    body = await response.text()
                    key = url.split("/api/v1/")[1]
                    captured[key] = json.loads(body)
                except:
                    pass

        page.on("response", on_response)

        print("Loading SofaScore WC2026...")
        await page.goto(
            "https://www.sofascore.com/football/tournament/world/world-championship/16#id:58210",
            wait_until="domcontentloaded", timeout=45000
        )
        await asyncio.sleep(10)

        # Click Standings tab
        try:
            tabs = page.locator("a, button, [role='tab']")
            count = await tabs.count()
            for i in range(count):
                text = (await tabs.nth(i).text_content() or "").strip()
                if text == "Standings":
                    await tabs.nth(i).click()
                    await asyncio.sleep(4)
                    break
        except:
            pass

        print(f"Captured {len(captured)} API responses")

        # Save key datasets
        for key, data in captured.items():
            safe = key.replace("/", "_").replace("?", "_")[:80]
            save_json(f"cap_{safe}", data)

        # Build summary
        events = []
        for k, v in captured.items():
            if isinstance(v, dict) and "events" in v:
                for ev in v["events"]:
                    eid = ev.get("id")
                    if eid and not any(e.get("id") == eid for e in events):
                        events.append(ev)
        save_json("all_events", {"events": events})

        for k, v in captured.items():
            if "standings" in k and isinstance(v, dict) and "standings" in v:
                save_json("standings", v)
                break

        completed = [e for e in events if e.get("status", {}).get("type") == "finished"]
        upcoming = [e for e in events if e.get("homeTeam", {}).get("name") and e.get("status", {}).get("type") != "finished"]

        print(f"\nResults: {len(events)} events ({len(completed)} completed, {len(upcoming)} upcoming)")
        for ev in events:
            ht = ev.get("homeTeam", {}).get("name", "?")
            at = ev.get("awayTeam", {}).get("name", "?")
            hs = ev.get("homeScore", {}).get("current")
            as_ = ev.get("awayScore", {}).get("current")
            st = ev.get("status", {}).get("description", "?")
            if hs is not None:
                print(f"  {ht} {hs}-{as_} {at}  [{st}]")
            else:
                print(f"  {ht} vs {at}  [{st}]")

        print(f"\nData saved to {OUTDIR}")
        print("Run: python scrapers/sofascore_integrate.py")

        await browser.close()

asyncio.run(main())
