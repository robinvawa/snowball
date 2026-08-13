"""Video-level scoring: perpetuity views, age-neutral outlier, cross-distributor
consensus, and a composite interest score."""
import collections
import datetime as dt
import json
import os
import re
import statistics

import extract
import scope

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Saturation curve supplied by the user: the share of a video's perpetuity
# views already accumulated at age d. Reaches 1.0 at d=1278 (~3.5 years).
HORIZON = 1278
_ZH = (1279 / 290.9357027) ** 0.672538774
_DEN = _ZH / (1 + _ZH)


def maturity(days):
    d = max(0, min(days, HORIZON))
    z = ((d + 1) / 290.9357027) ** 0.672538774
    return (z / (1 + z)) / _DEN


def age_days(published, today):
    try:
        p = dt.datetime.strptime(published[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    return (today - p).days


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def pct_ranks(values):
    """Percentile rank in [0,1] for each value, ties share a rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    n = max(1, len(values) - 1)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = ((i + j) / 2) / n
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def load_videos(today):
    """Full catalogues first — they are complete. The 50-video harvests only
    fill in channels the full-catalogue pass could not reach, otherwise a
    channel's older uploads silently vanish from the tables while still
    counting in its channel-level stats."""
    vids = {}
    for f in ("seed_videos.json", "discovered_videos.json", "full_videos.json"):
        p = os.path.join(DATA, f)
        if os.path.exists(p):
            for v in json.load(open(p)):
                vids[v["video_id"]] = v  # dedupe across sources
    vids = list(vids.values())
    # Recompute attributions from scratch: full_catalog only extracted the
    # title handles, so description credits were missing on most of the set.
    extract.enrich(vids)
    scope.apply(vids)
    for v in vids:
        v["age_days"] = age_days(v["published"], today)
    return [v for v in vids if v["age_days"] is not None and v["age_days"] >= 0]


def score(vids, dist_ids):
    """Attach perpetuity + composite interest score. Only distributor channels."""
    vids = [v for v in vids if v["channel_id"] in dist_ids]

    for v in vids:
        m = maturity(v["age_days"])
        v["maturity"] = round(m, 4)
        v["perpetuity_views"] = round(v["views"] / m) if m else v["views"]
        v["confidence"] = ("alta" if v["age_days"] >= 90 else
                           "media" if v["age_days"] >= 21 else "baja")

    # Age-neutral outlier: projected lifetime views against the channel's own
    # median. The baseline counts only in-scope videos — off-topic uploads drag
    # it down and inflate every outlier, the same way shorts used to. On
    # 22TechZoom the median moves from 3,206 to 43,596 once they are excluded.
    by_ch = collections.defaultdict(list)
    for v in vids:
        if v["scope"] == "in":
            by_ch[v["channel_id"]].append(v["perpetuity_views"])
    for v in vids:  # channels with no in-scope video still need a baseline
        by_ch.setdefault(v["channel_id"], []).append(v["perpetuity_views"])
    med = {c: (statistics.median(x) or 1) for c, x in by_ch.items()}
    for v in vids:
        base = med[v["channel_id"]] or 1
        v["perp_outlier"] = round(v["perpetuity_views"] / base, 2)

    # Cross-distributor consensus, computed on in-scope videos only: how many
    # distinct distributors covered this source creator, and how many of them
    # beat their own baseline on it.
    cov = collections.defaultdict(set)
    win = collections.defaultdict(set)
    for v in vids:
        if v["scope"] == "out":
            continue
        for h in v["source_handles_title"]:
            k = norm(h)
            if not k:
                continue
            cov[k].add(v["channel_id"])
            if v["perp_outlier"] >= 1.5:
                win[k].add(v["channel_id"])
    for v in vids:
        ks = [norm(h) for h in v["source_handles_title"] if norm(h)]
        v["xd_distributors"] = max([len(cov[k]) for k in ks], default=0)
        v["xd_winners"] = max([len(win[k]) for k in ks], default=0)

    # Composite score over in-scope videos.
    pool = [v for v in vids if v["scope"] != "out"]
    if pool:
        r_out = pct_ranks([v["perp_outlier"] for v in pool])
        r_reach = pct_ranks([v["perpetuity_views"] for v in pool])
        r_eng = pct_ranks([v["likes"] / max(1, v["views"]) for v in pool])
        for i, v in enumerate(pool):
            cons = min(1.0, max(0, v["xd_winners"] - 1) / 3.0)
            raw = (0.34 * r_out[i] + 0.28 * r_reach[i] +
                   0.28 * cons + 0.10 * r_eng[i])
            # Damp only the very young, where perpetuity is a wild extrapolation.
            if v["age_days"] < 21:
                raw *= 0.75 + 0.25 * (v["age_days"] / 21)
            v["interest"] = round(100 * raw, 1)
    for v in vids:
        v.setdefault("interest", 0.0)

    vids.sort(key=lambda v: -v["interest"])
    return vids


def main(today=None):
    today = today or dt.date.today()
    rows = json.load(open(os.path.join(DATA, "channels.json")))
    dist_ids = {r["channel_id"] for r in rows
                if r["tier"] == "A" or r.get("attribution_rate", 0) >= 0.3}
    dist_ids -= {r["channel_id"] for r in rows
                 if norm(r["title"]) == "quantummakers"}
    vids = score(load_videos(today), dist_ids)
    json.dump(vids, open(os.path.join(DATA, "scored_videos.json"), "w"),
              indent=1)
    inn = [v for v in vids if v["scope"] == "in"]
    print("Videos de distribuidores: %d  (in=%d, unsure=%d, out=%d)" % (
        len(vids), len(inn),
        sum(1 for v in vids if v["scope"] == "unsure"),
        sum(1 for v in vids if v["scope"] == "out")))
    print("Confianza: alta=%d media=%d baja=%d" % (
        sum(1 for v in inn if v["confidence"] == "alta"),
        sum(1 for v in inn if v["confidence"] == "media"),
        sum(1 for v in inn if v["confidence"] == "baja")))
    return vids


if __name__ == "__main__":
    main()
