"""Refresh the whole dataset against the live API, in one command.

    python3 refresh.py

What it does, in order:
1. Rolls the current full_videos.json into data/views_prev.json — that snapshot
   is what the "Desde el último refresh" tab measures growth against.
2. Archives the stats caches (channels/playlistItems/videos) so every stat is
   re-fetched fresh. The search cache is kept: searches cost 100 units each and
   their results (which channels exist) do not go stale the way view counts do.
3. Re-downloads every distributor's full catalogue and QM's own catalogue.
   Cost measured on 25 ago 2026: ~600 units of the 10,000 daily — safe to run
   weekly or even daily.
4. Rebuilds the dashboard.
"""
import datetime as dt
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "cache")


def main():
    fv = os.path.join(DATA, "full_videos.json")
    try:
        vids = json.load(open(fv))
    except Exception:
        vids = []
    if vids:
        stamp = dt.date.fromtimestamp(os.path.getmtime(fv)).isoformat()
        json.dump({"date": stamp,
                   "views": {v["video_id"]: v["views"] for v in vids}},
                  open(os.path.join(DATA, "views_prev.json"), "w"))
        print("snapshot previo guardado: %d vídeos, datos del %s"
              % (len(vids), stamp))

    stale = os.path.join(DATA, "cache_stale")
    shutil.rmtree(stale, ignore_errors=True)
    os.makedirs(stale, exist_ok=True)
    for d in ("channels", "playlistItems", "videos"):
        p = os.path.join(CACHE, d)
        if os.path.isdir(p):
            shutil.move(p, os.path.join(stale, d))
    print("caché de stats apartada (la de búsquedas se conserva)")

    for f in ("full_catalog.json",):
        try:
            os.remove(os.path.join(DATA, f))
        except FileNotFoundError:
            pass
    json.dump([], open(fv, "w"))

    import full_catalog
    full_catalog.main()
    import qm
    qm.harvest()
    import build_page
    build_page.main()
    shutil.rmtree(stale, ignore_errors=True)
    print("\nRefresh completo.")


if __name__ == "__main__":
    main()
