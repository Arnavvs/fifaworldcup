"""
SofaScore WC2026 player data scraper.

Strategy: navigate the SofaScore UI so the page's own API calls fire, then
intercept JSON responses (direct fetch() is Cloudflare-blocked).

Per-player data captured (defence / GK / midfield / attacking relevant):
  - attribute-overviews : FIFA-style radar (attacking, technical, tactical,
                          defending, creativity) -- the "player ratings"
  - characteristics     : positions + strength/weakness ranks
  - national-team-statistics : career international apps + goals
  - events/last/0       : recent matches with per-match SofaScore ratings

Phases:
  1. Squads  - team page -> Players tab -> collect player IDs from image calls
  2. Players - player page -> capture all player/{id}/* endpoints + name

Resumable: skips squad/player files already on disk.

Run (Playwright env):
  C:\\Users\\HP\\anaconda3\\envs\\minorproject\\python.exe scrapers/sofascore_players.py [--limit-teams N] [--test]
"""
import asyncio
import json
import os
import sqlite3
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "fifa_wc_data" / "db" / "football.db"
OUTDIR = Path(__file__).resolve().parent / "sofascore_players"
SQUAD_DIR = OUTDIR / "squads"
PLAYER_DIR = OUTDIR / "players"
for d in (OUTDIR, SQUAD_DIR, PLAYER_DIR):
    d.mkdir(parents=True, exist_ok=True)


def get_teams():
    con = sqlite3.connect(str(DB))
    rows = con.execute(
        "SELECT DISTINCT home_team AS t, home_team_id AS tid FROM sofascore_events WHERE home_team_id IS NOT NULL "
        "UNION SELECT DISTINCT away_team, away_team_id FROM sofascore_events WHERE away_team_id IS NOT NULL "
        "ORDER BY 1"
    ).fetchall()
    con.close()
    return [(t, tid) for t, tid in rows]


def slugify(name):
    return name.lower().replace(" ", "-").replace("&", "and").replace("'", "").replace(".", "")


async def click_tab(page, label):
    try:
        tabs = page.locator("a, button, [role='tab']")
        n = await tabs.count()
        for i in range(n):
            t = (await tabs.nth(i).text_content() or "").strip()
            if t == label:
                await tabs.nth(i).click()
                return True
    except:
        pass
    return False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-teams", type=int, default=None)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        args.limit_teams = 1

    from playwright.async_api import async_playwright

    teams = get_teams()
    if args.limit_teams:
        teams = teams[:args.limit_teams]

    captured = {}
    img_ids = set()  # player ids seen via image calls

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome", args=["--window-size=1200,800"])
        ctx = await browser.new_context(viewport={"width": 1200, "height": 800})
        page = await ctx.new_page()

        async def on_response(response):
            url = response.url
            if "/api/v1/" not in url:
                return
            key = url.split("/api/v1/")[1]
            m = re.match(r"player/(\d+)/image", key)
            if m:
                img_ids.add(int(m.group(1)))
                return
            if response.status == 200 and "image" not in key:
                try:
                    captured[key] = json.loads(await response.text())
                except:
                    pass

        page.on("response", on_response)

        print("Warming up session...")
        await page.goto(
            "https://www.sofascore.com/football/tournament/world/world-championship/16#id:58210",
            wait_until="domcontentloaded", timeout=45000
        )
        await asyncio.sleep(6)

        # ============ PHASE 1: SQUADS ============
        print(f"\n=== PHASE 1: Squads ({len(teams)} teams) ===")
        squads = {}  # team -> list of player ids
        for team, tid in teams:
            squad_file = SQUAD_DIR / f"team_{tid}.json"
            if squad_file.exists():
                squads[team] = json.loads(squad_file.read_text(encoding="utf-8"))["player_ids"]
                print(f"  {team}: cached ({len(squads[team])} players)")
                continue
            img_ids.clear()
            slug = slugify(team)
            url = f"https://www.sofascore.com/team/football/{slug}/{tid}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                await click_tab(page, "Players")
                await asyncio.sleep(3)
                # scroll to force lazy-loaded squad images
                for _ in range(8):
                    await page.mouse.wheel(0, 900)
                    await asyncio.sleep(0.6)
                await asyncio.sleep(2)
                pids = sorted(img_ids)
                squad_file.write_text(json.dumps({"team": team, "team_id": tid, "player_ids": pids}, indent=2), encoding="utf-8")
                squads[team] = pids
                print(f"  {team}: {len(pids)} players")
            except Exception as e:
                print(f"  {team}: error {e}")
                squads[team] = []

        all_players = [(team, tid, pid) for team, tid in teams for pid in squads.get(team, [])]
        # dedupe by player id (a player belongs to one nation)
        seen = set()
        uniq = []
        for team, tid, pid in all_players:
            if pid not in seen:
                seen.add(pid)
                uniq.append((team, tid, pid))
        print(f"\nTotal unique players: {len(uniq)}")

        # ============ PHASE 2: PLAYER PROFILES ============
        print(f"\n=== PHASE 2: Player profiles ===")
        done = 0
        for team, tid, pid in uniq:
            pfile = PLAYER_DIR / f"player_{pid}.json"
            if pfile.exists():
                done += 1
                continue
            # clear this player's captures
            for k in list(captured.keys()):
                if f"player/{pid}/" in k:
                    del captured[k]
            url = f"https://www.sofascore.com/player/-/{pid}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(3)
                await click_tab(page, "Statistics")
                await asyncio.sleep(2.5)

                # name from title: "Riyad Mahrez stats and ratings | Sofascore"
                name = "?"
                try:
                    title = await page.title()
                    name = re.split(r" stats| live score| - ", title)[0].strip()
                except:
                    pass

                # keep only relevant endpoints (drop media/posts/banners to stay lean)
                KEEP = {"attribute-overviews", "characteristics", "national-team-statistics", "unique-tournaments"}
                pdata = {"player_id": pid, "name": name, "team": team, "team_id": tid}
                for k, v in captured.items():
                    if f"player/{pid}/" not in k:
                        continue
                    part = k.split(f"player/{pid}/")[-1].replace("/", "_")
                    if part in KEEP:
                        pdata[part] = v
                    elif part == "events_last_0":
                        # compact recent form: just ratings + dates, not full match objects
                        smap = v.get("statisticsMap", {}) if isinstance(v, dict) else {}
                        ratings = []
                        for ev in (v.get("events", []) if isinstance(v, dict) else []):
                            eid = str(ev.get("id"))
                            st = smap.get(eid, {}) if isinstance(smap, dict) else {}
                            ratings.append({
                                "ts": ev.get("startTimestamp"),
                                "rating": st.get("rating"),
                                "minutes": st.get("minutesPlayed"),
                            })
                        pdata["recent_form"] = ratings

                pfile.write_text(json.dumps(pdata, indent=2, ensure_ascii=False), encoding="utf-8")
                has_attr = "attribute-overviews" in pdata
                print(f"  [{done+1}/{len(uniq)}] {name} ({team}): attr={'Y' if has_attr else 'N'}")
                done += 1
            except Exception as e:
                print(f"  pid {pid}: error {e}")

        print(f"\n=== DONE: {done}/{len(uniq)} players ===")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
