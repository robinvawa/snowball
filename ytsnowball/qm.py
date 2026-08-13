"""Harvest Quantum Makers' own catalogue and use it as ground truth.

Every other channel in this project is a proxy. Quantum Makers is the actual
target: same production level, same audience, same channel. So its results are
the only data that directly answers "would this creator work for us?", and the
only way to check whether the distributor-derived signals predict anything at
all.
"""
import collections
import datetime as dt
import json
import math
import os
import re
import statistics

import extract
import metrics
import scope
import shorts
import yt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
QM_HANDLE = "QuantumMakers"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def harvest(limit=600):
    ch = yt.channel_by_handle(QM_HANDLE)
    vids = yt.playlist_videos(yt.uploads_playlist(ch), limit=limit)
    recs = yt.videos(vids)
    today = dt.date.today()
    out = []
    for v in recs:
        st = v.get("statistics", {})
        secs = scope.iso_seconds(v.get("contentDetails", {}).get("duration", ""))
        if shorts.is_short(secs, v["id"]):
            continue  # same rule as every distributor
        out.append({
            "video_id": v["id"],
            "channel_id": v["snippet"]["channelId"],
            "channel_title": "Quantum Makers",
            "title": v["snippet"]["title"],
            "description": (v["snippet"].get("description") or "")[:1500],
            "published": v["snippet"]["publishedAt"],
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "duration": v.get("contentDetails", {}).get("duration", ""),
            "tags": v["snippet"].get("tags", [])[:25],
        })
    extract.enrich(out)
    scope.apply(out)
    for v in out:
        v["age_days"] = metrics.age_days(v["published"], today)

    # Same treatment every distributor gets, so the numbers are comparable.
    live = [v for v in out if v["age_days"] is not None and v["scope"] != "out"]
    for v in live:
        m = metrics.maturity(v["age_days"])
        v["maturity"] = round(m, 4)
        v["perpetuity_views"] = round(v["views"] / m) if m else v["views"]
    med = statistics.median([v["perpetuity_views"] for v in live])
    for v in live:
        v["perp_outlier"] = round(v["perpetuity_views"] / med, 2)
        v["source_handle"] = (v["source_handles_title"] or [None])[0]

    json.dump(live, open(os.path.join(DATA, "qm_videos.json"), "w"), indent=1)
    return live, med


if __name__ == "__main__":
    live, med = harvest()
    att = [v for v in live if v["source_handles_title"]]
    print("Vídeos de Quantum Makers en scope: %d" % len(live))
    print("Con creador acreditado en el título: %d (%.0f%%)"
          % (len(att), 100 * len(att) / len(live)))
    print("Mediana de views a perpetuidad: %s" % f"{round(med):,}")
    print("Creadores fuente distintos: %d"
          % len({norm(h) for v in att for h in v["source_handles_title"]}))
    print("Cuota usada: %d" % yt.quota_used())
    print()
    live.sort(key=lambda v: -v["perp_outlier"])
    print("Vuestros 10 mayores outliers:")
    for v in live[:10]:
        print("  x%-6.1f %11s perp.  %-14s %s" % (
            v["perp_outlier"], f"{v['perpetuity_views']:,}",
            "@" + (v["source_handle"] or "—")[:13], v["title"][:46]))
