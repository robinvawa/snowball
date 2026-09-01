"""Snowball: search each source-creator handle, collect the channels that
covered it. A channel covering 2+ pool creators is a distributor."""
import collections
import datetime as dt
import json
import os
import re
import sys
import time

import extract
import yt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Our own channel must never end up in the distributor list.
OWN = {"quantum makers", "quantummakers"}

RECHECK_DAYS = 14
DAILY_QUOTA = 10000
RESERVE = 1200  # keep room for the cheap channel/video lookups afterwards


def norm(h):
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def rank_creators(videos, already_searched):
    """Rank source creators by how many distinct distributors covered them,
    tie-broken by the best outlier multiple any distributor got on them."""
    cover = collections.defaultdict(set)
    best = collections.defaultdict(float)
    orig = {}
    for v in videos:
        for h in v["source_handles_title"]:
            k = norm(h)
            if not k:
                continue
            cover[k].add(v["channel_id"])
            best[k] = max(best[k], v.get("outlier", 0))
            orig.setdefault(k, h)
    ranked = sorted(cover, key=lambda k: (-len(cover[k]), -best[k]))
    return [(k, orig[k], len(cover[k]), best[k])
            for k in ranked if k not in already_searched]


def run(videos, max_searches=40, attr=None):
    state_path = os.path.join(DATA, "snowball_state.json")
    try:
        state = json.load(open(state_path))
    except Exception:
        state = {"searched": [], "hits": {}}
    searched = set(state["searched"])
    searched_at = state.get("searched_at", {})
    hits = collections.defaultdict(dict)
    for cid, rec in state["hits"].items():
        hits[cid] = rec

    todo = rank_creators(videos, searched)
    # Con el ranking v2 disponible, la cola se ordena por views atribuibles:
    # buscar primero a los creadores mas valiosos, que son cuyas coberturas
    # (conocidas y por descubrir) mas importan.
    if attr:
        todo.sort(key=lambda t: -attr.get(t[0], 0))
    print("Candidate source creators not yet searched: %d" % len(todo))

    # Cola de re-búsqueda: un creador buscado hace >= RECHECK_DAYS puede tener
    # distribuidores NUEVOS cubriéndolo desde entonces, y esa es la única vía
    # por la que un canal recién nacido entra al mapa. Solo se consume cuando
    # la cola de creadores nunca buscados se ha agotado, más antiguos primero
    # y a igual fecha los de más views atribuibles.
    label = {}
    for v in videos:
        for h in v["source_handles_title"]:
            label.setdefault(norm(h), h)
    cutoff = (dt.date.today() - dt.timedelta(days=RECHECK_DAYS)).isoformat()
    stale = [k for k in searched
             if searched_at.get(k, "2026-08-11") <= cutoff and k in label]
    stale.sort(key=lambda k: (searched_at.get(k, "2026-08-11"),
                              -(attr or {}).get(k, 0)))
    # Nuevos y re-búsquedas compiten en la misma cola por views atribuibles:
    # re-buscar a un creador top al mes rinde más que estrenar al creador
    # número 800 de la cola. Sin ranking de valor, los nuevos van primero.
    queue = [(k, h, n, o, False) for k, h, n, o in todo] + \
            [(k, label[k], 0, 0.0, True) for k in stale]
    if attr:
        queue.sort(key=lambda t: -attr.get(t[0], 0))
    if stale:
        print("Re-search queue (last searched >= %dd ago): %d"
              % (RECHECK_DAYS, len(stale)))

    done = 0
    stop = False
    for key, handle, ncov, outlier, fresh in queue:
        if done >= max_searches or stop:
            break
        if yt.quota_used() > DAILY_QUOTA - RESERVE - 100:
            print("\n!! Quota guard hit, stopping searches.")
            break
        try:
            items = yt.search('"%s"' % handle, max_results=50, fresh=fresh)
        except yt.QuotaExceeded:
            print("\n!! API reports quota exhausted.")
            stop = True
            break
        done += 1
        searched.add(key)
        searched_at[key] = time.strftime("%Y-%m-%d")
        new = 0
        for it in items:
            sn = it["snippet"]
            cid, ctitle = sn["channelId"], sn["channelTitle"]
            title = sn["title"]
            # Skip the original creator's own channel.
            if norm(ctitle) == key or key in norm(ctitle):
                continue
            if norm(ctitle) in {norm(o) for o in OWN}:
                continue
            # Require the attribution pattern: this is a repost/edit, not the
            # creator's own upload or unrelated content.
            if key not in norm(title):
                continue
            rec = hits.setdefault(cid, {"channel_title": ctitle,
                                        "creators": [], "examples": []})
            if key not in rec["creators"]:
                rec["creators"].append(key)
                new += 1
            if len(rec["examples"]) < 3:
                rec["examples"].append({"video_id": it["id"]["videoId"],
                                        "title": title})
        print("  [%2d] @%-26s covered_by=%d best_x=%-6.1f -> %2d new links (quota %d)"
              % (done, handle[:26], ncov, outlier, new, yt.quota_used()))

    state = {"searched": sorted(searched), "searched_at": searched_at,
             "hits": dict(hits)}
    json.dump(state, open(state_path, "w"), indent=1)
    print("\nSearches this run: %d | quota used today: %d" % (done, yt.quota_used()))
    print("Channels seen: %d" % len(hits))
    return state


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    # Pool completo: catalogos enteros + creditos de descripcion resueltos,
    # en vez de las muestras de 50 videos de la primera era.
    scored = os.path.join(DATA, "scored_videos.json")
    if os.path.exists(scored):
        vids = [v for v in json.load(open(scored)) if v.get("scope") != "out"]
        for v in vids:
            v["outlier"] = v.get("perp_outlier", 0)
        try:
            attr = {c["key"]: c["attr_views"] for c in json.load(
                open(os.path.join(DATA, "creator_odds.json")))["creators"]}
        except Exception:
            attr = None
        run(vids, n, attr)
        raise SystemExit
    vids = json.load(open(os.path.join(DATA, "seed_videos.json")))
    disc = os.path.join(DATA, "discovered_videos.json")
    if os.path.exists(disc):  # iteration 2+: rank over the expanded pool
        vids += json.load(open(disc))
    vids = extract.enrich(vids)
    run(vids, max_searches=n)
