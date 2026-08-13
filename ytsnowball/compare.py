"""Ecosystem-level comparison: the distributors as a whole, and against us.

The question that matters operationally is not how big they are, it is which of
them ever get to a creator *before* we do. A channel that only ever publishes
after us is a mirror, not a radar: it can never tell us anything we did not
already know.
"""
import collections
import datetime as dt
import json
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Our name, and the near-misses that a typo-squat would use.
BRAND_WORDS = {"quantum": 0.6, "makers": 0.4, "maker": 0.25}


def _lev(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load():
    dv = [v for v in json.load(open(os.path.join(DATA, "scored_videos.json")))
          if v["scope"] != "out"]
    qm = [v for v in json.load(open(os.path.join(DATA, "qm_videos.json")))
          if v.get("scope") != "out"]
    ch = {c["channel_id"]: c for c in
          json.load(open(os.path.join(DATA, "channels.json")))}
    cc = json.load(open(os.path.join(DATA, "creator_channels.json")))
    return dv, qm, ch, cc


def creator_index(vids):
    by = collections.defaultdict(list)
    for v in vids:
        for h in v["source_handles_title"]:
            k = norm(h)
            if k:
                by[k].append(v)
    return by


def brand_similarity(title):
    """How much a channel name impersonates ours.

    'maker'/'makers' alone is the generic vocabulary of this niche — half the
    ecosystem uses it and it means nothing. The distinctive element is
    'quantum', so a name only counts as a squat if it carries that (or a
    one-letter miss of it, which is exactly what a typo-squat looks like).
    """
    words = re.findall(r"[a-z]+", (title or "").lower())
    if not words:
        return 0.0, []
    qhit = None
    for w in words:
        if abs(len(w) - 7) <= 2:
            d = _lev(w, "quantum")
            if d <= 2 and (qhit is None or d < qhit[1]):
                qhit = (w, d)
    # A lone "Q" next to a maker word is the compressed version of the same idea.
    lone_q = "q" in words and any(_lev(w, "makers") <= 1 or _lev(w, "maker") <= 1
                                  for w in words)
    if not qhit and not lone_q:
        return 0.0, []

    hits, score = [], 0.0
    if qhit:
        score += 0.65 if qhit[1] == 0 else 0.55
        hits.append(qhit[0] if qhit[1] == 0 else "%s (~quantum)" % qhit[0])
    else:
        score += 0.35
        hits.append("Q (~quantum)")
    for w in words:
        if _lev(w, "makers") <= 1 or _lev(w, "maker") <= 1:
            score += 0.35
            hits.append(w if w in ("maker", "makers") else "%s (~makers)" % w)
            break
    return min(1.0, round(score, 2)), hits


def build():
    dv, qm, ch, cc = load()
    d_by = creator_index(dv)
    q_by = creator_index(qm)
    qm_creators, d_creators = set(q_by), set(d_by)

    # First publication date per creator, ours and theirs.
    q_first = {k: min(v["published"][:10] for v in vs) for k, vs in q_by.items()}
    label = {}
    for k, vs in d_by.items():
        label[k] = next((h for v in vs for h in v["source_handles_title"]
                         if norm(h) == k), k)
    for k, vs in q_by.items():
        label.setdefault(k, next((h for v in vs for h in v["source_handles_title"]
                                  if norm(h) == k), k))

    # Per-distributor behaviour against us.
    per = {}
    for v in dv:
        cid = v["channel_id"]
        p = per.setdefault(cid, {"videos": 0, "creators": set(), "lead": 0,
                                 "follow": 0, "lags": [], "own": set()})
        p["videos"] += 1
        for h in v["source_handles_title"]:
            k = norm(h)
            if not k:
                continue
            p["creators"].add(k)
            if k in q_first:
                if v["published"][:10] < q_first[k]:
                    p["lead"] += 1
                else:
                    p["follow"] += 1
                    d0 = dt.date.fromisoformat(v["published"][:10])
                    d1 = dt.date.fromisoformat(q_first[k])
                    p["lags"].append((d0 - d1).days)
            else:
                p["own"].add(k)

    rows = []
    for cid, p in per.items():
        c = ch.get(cid)
        if not c or not p["creators"]:
            continue
        n = len(p["creators"])
        shared = len(p["creators"] & qm_creators)
        sim, toks = brand_similarity(c["title"])
        rows.append({
            "channel_id": cid, "title": c["title"], "handle": c["handle"],
            "url": c["url"], "subs": c["subs"], "videos_seen": p["videos"],
            "creators": n,
            "shared": shared,
            "overlap_pct": round(100 * shared / n),
            "exclusive": n - shared,
            "lead": p["lead"], "follow": p["follow"],
            "lead_pct": round(100 * p["lead"] / max(1, p["lead"] + p["follow"])),
            "median_lag": (round(statistics.median(p["lags"]))
                           if p["lags"] else None),
            "brand_sim": round(sim, 2), "brand_tokens": toks,
        })
    rows.sort(key=lambda r: -r["creators"])

    # Creators the ecosystem covers a lot and we have never touched.
    gap = []
    for k in d_creators - qm_creators:
        vs = d_by[k]
        chans = {v["channel_id"] for v in vs}
        m = cc.get(k) or {}
        gap.append({
            "creator": label[k],
            "url": "https://www.youtube.com/@%s" % label[k],
            "distributors": len(chans),
            "videos": len(vs),
            "best_reach": max(v["perpetuity_views"] for v in vs),
            "best_outlier": round(max(v["perp_outlier"] for v in vs), 1),
            "best_title": max(vs, key=lambda v: v["perpetuity_views"])["title"],
            "best_video": max(vs, key=lambda v: v["perpetuity_views"])["video_id"],
            "creator_subs": m.get("subs") if m.get("found") else None,
            "last_seen": max(v["published"][:10] for v in vs),
        })
    gap.sort(key=lambda g: (-g["distributors"], -g["best_reach"]))

    # Aggregate ecosystem vs us. Perpetuity throughout: comparing raw view
    # counts across channels penalises whoever published more recently.
    d_views = sum(v["perpetuity_views"] for v in dv)
    q_views = sum(v["perpetuity_views"] for v in qm)
    agg = {
        "n_distributors": len(rows),
        "d_videos": len(dv), "q_videos": len(qm),
        "d_views": d_views, "q_views": q_views,
        "d_median_views": round(statistics.median(
            [v["perpetuity_views"] for v in dv])),
        "q_median_views": round(statistics.median(
            [v["perpetuity_views"] for v in qm])),
        "d_raw_views": sum(v["views"] for v in dv),
        "q_raw_views": sum(v["views"] for v in qm),
        "d_median_dur": round(statistics.median([v.get("seconds", 0) for v in dv])),
        "q_median_dur": round(statistics.median([v.get("seconds", 0) for v in qm])),
        "d_creators": len(d_creators), "q_creators": len(qm_creators),
        "shared_creators": len(d_creators & qm_creators),
        "only_theirs": len(d_creators - qm_creators),
        "only_ours": len(qm_creators - d_creators),
        "overlap_of_ours": round(100 * len(d_creators & qm_creators)
                                 / max(1, len(qm_creators))),
        "overlap_of_theirs": round(100 * len(d_creators & qm_creators)
                                   / max(1, len(d_creators))),
        "total_lead": sum(r["lead"] for r in rows),
        "total_follow": sum(r["follow"] for r in rows),
    }

    # Topic mix, ours vs theirs.
    def topic_share(vids):
        c = collections.Counter(t for v in vids for t in v.get("topics", []))
        tot = sum(c.values()) or 1
        return {k: 100 * n / tot for k, n in c.items()}
    ts_d, ts_q = topic_share(dv), topic_share(qm)
    topics = []
    for t in set(ts_d) | set(ts_q):
        topics.append({"topic": t, "them": round(ts_d.get(t, 0), 1),
                       "us": round(ts_q.get(t, 0), 1),
                       "gap": round(ts_d.get(t, 0) - ts_q.get(t, 0), 1)})
    topics.sort(key=lambda x: -(x["them"] + x["us"]))

    out = {"agg": agg, "channels": rows, "gap": gap, "topics": topics}
    json.dump(out, open(os.path.join(DATA, "comparison.json"), "w"), indent=1)
    return out


if __name__ == "__main__":
    o = build()
    a = o["agg"]
    print("ECOSISTEMA vs QUANTUM MAKERS")
    print("  vídeos      : %d ellos / %d nosotros" % (a["d_videos"], a["q_videos"]))
    print("  views suma  : %s ellos / %s nosotros"
          % (f"{a['d_views']:,}", f"{a['q_views']:,}"))
    print("  mediana view: %s ellos / %s nosotros  (x%.0f)"
          % (f"{a['d_median_views']:,}", f"{a['q_median_views']:,}",
             a["q_median_views"] / max(1, a["d_median_views"])))
    print("  duración med: %ds ellos / %ds nosotros"
          % (a["d_median_dur"], a["q_median_dur"]))
    print()
    print("POOL DE CREADORES")
    print("  suyos %d | nuestros %d | compartidos %d"
          % (a["d_creators"], a["q_creators"], a["shared_creators"]))
    print("  %d%% de los nuestros los tocan ellos" % a["overlap_of_ours"])
    print("  %d%% de los suyos los hemos tocado nosotros" % a["overlap_of_theirs"])
    print("  solo suyos: %d  |  solo nuestros: %d"
          % (a["only_theirs"], a["only_ours"]))
    print()
    print("QUIÉN LLEGA ANTES (sobre creadores compartidos)")
    print("  publicaciones suyas ANTES que la nuestra: %d" % a["total_lead"])
    print("  publicaciones suyas DESPUÉS:              %d" % a["total_follow"])
    print()
    scouts = [r for r in o["channels"] if r["lead"] >= 2]
    scouts.sort(key=lambda r: -r["lead"])
    print("RADARES: distribuidores que más veces han llegado antes que nosotros")
    for r in scouts[:10]:
        print("  %-24s %2d veces antes / %2d después | %d creadores, %d%% exclusivos"
              % (r["title"][:24], r["lead"], r["follow"], r["creators"],
                 100 - r["overlap_pct"]))
    print()
    print("HUECO: creadores que ellos cubren mucho y nosotros nunca — top 12")
    for g in o["gap"][:12]:
        print("  %-26s %2d distribuidores  pico %10s  %s subs" % (
            g["creator"][:26], g["distributors"], f"{g['best_reach']:,}",
            f"{g['creator_subs']:,}" if g["creator_subs"] else "?"))
