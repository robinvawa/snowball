"""Snowball via yt-dlp: the searches, without the API and without its caps.

Run this ON YOUR OWN MACHINE (the remote Claude environment cannot reach
youtube.com; your residential IP also survives scraping far better than a
datacenter one):

    pip install yt-dlp
    python3 snowball_dlp.py           # whole queue (new + rechecks)
    python3 snowball_dlp.py 100       # cap at 100 searches

It reads ONLY committed files (creator_odds.json for the value-ranked queue,
snowball_state.json for what was already searched and when), so a fresh
`git pull` is all it needs — no .env, no API key, no derived data.

It writes the same snowball_state.json the API snowball writes, with the same
shape, so the normal chain (classify -> verify -> full_catalog -> build_page)
picks the results up unchanged. Searches are spaced 3-6s apart to be gentle;
failures are skipped WITHOUT marking the creator as searched, and state is
saved every 10 searches, so Ctrl-C loses nothing.
"""
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

RECHECK_DAYS = 14
OWN = {"quantummakers", "quantum makers"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def ytdlp_search(handle, n=50):
    out = subprocess.run(
        ["yt-dlp", "--flat-playlist", "-J", "--no-warnings",
         'ytsearch%d:"%s"' % (n, handle)],
        capture_output=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or b"")[-200:].decode(errors="replace"))
    return json.loads(out.stdout).get("entries") or []


def main(limit=None):
    odds = json.load(open(os.path.join(DATA, "creator_odds.json")))["creators"]
    state_path = os.path.join(DATA, "snowball_state.json")
    state = json.load(open(state_path))
    searched = set(state["searched"])
    searched_at = state.get("searched_at", {})
    hits = state["hits"]

    cutoff = (dt.date.today() - dt.timedelta(days=RECHECK_DAYS)).isoformat()
    queue = []
    for c in odds:  # ya viene ordenado por views atribuibles
        k = c["key"]
        if k not in searched:
            queue.append((k, c["creator"], False))
        elif searched_at.get(k, "2026-08-11") <= cutoff:
            queue.append((k, c["creator"], True))
    if limit:
        queue = queue[:limit]
    print("Cola: %d busquedas (%d nuevas, %d re-busquedas)"
          % (len(queue), sum(1 for q in queue if not q[2]),
             sum(1 for q in queue if q[2])))

    done = fails = 0
    for i, (key, handle, fresh) in enumerate(queue, 1):
        try:
            entries = ytdlp_search(handle)
        except Exception as e:
            fails += 1
            print("  [%3d] @%-26s FALLO (%s)" % (i, handle[:26], str(e)[:60]))
            if fails >= 8:
                print("!! Demasiados fallos seguidos: YouTube esta cortando. "
                      "Para y reintenta mas tarde.")
                break
            time.sleep(20)
            continue
        fails = 0
        done += 1
        searched.add(key)
        searched_at[key] = time.strftime("%Y-%m-%d")
        new = 0
        for e in entries:
            ctitle = e.get("channel") or e.get("uploader") or ""
            cid = e.get("channel_id") or ""
            title = e.get("title") or ""
            if not cid or not ctitle:
                continue
            if norm(ctitle) == key or key in norm(ctitle):
                continue
            if norm(ctitle) in {norm(o) for o in OWN}:
                continue
            if key not in norm(title):
                continue
            rec = hits.setdefault(cid, {"channel_title": ctitle,
                                        "creators": [], "examples": []})
            if key not in rec["creators"]:
                rec["creators"].append(key)
                new += 1
            if len(rec["examples"]) < 3:
                rec["examples"].append({"video_id": e.get("id", ""),
                                        "title": title})
        tag = "re" if fresh else "  "
        print("  [%3d]%s @%-26s -> %2d enlaces nuevos  (canales: %d)"
              % (i, tag, handle[:26], new, len(hits)))
        if done % 10 == 0:
            json.dump({"searched": sorted(searched),
                       "searched_at": searched_at, "hits": hits},
                      open(state_path, "w"), indent=1)
        time.sleep(random.uniform(3, 6))

    json.dump({"searched": sorted(searched), "searched_at": searched_at,
               "hits": hits}, open(state_path, "w"), indent=1)
    print("\nHecho: %d busquedas. Ahora: git add data/snowball_state.json "
          "&& git commit && git push — y el resto de la cadena corre en "
          "remoto con la API." % done)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
