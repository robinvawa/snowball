"""Fetch every distributor's complete catalogue, shorts excluded.

The per-video tables were already clean, but the channel-level columns were not:
'Vídeos' came from YouTube's own videoCount, which counts shorts, and 'Fuentes'
came from the snowball hits rather than from what the channel actually publishes.
Pulling the full catalogue fixes both, and makes the creator count a real figure
over everything the channel has posted instead of a sample of 50.
"""
import collections
import datetime as dt
import json
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
OUT = os.path.join(DATA, "full_catalog.json")
VIDEOS_OUT = os.path.join(DATA, "full_videos.json")
RESERVE = 120

# Recent-activity window, in days since publication. The lower bound keeps out
# videos too young for the perpetuity projection to mean anything (at 12 days it
# still multiplies by 6.6x); the upper bound is wide enough that channels which
# publish rarely still land several videos inside it.
RECENT_MIN = 12
RECENT_MAX = 150


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main(limit_per_channel=400):
    rows = json.load(open(os.path.join(DATA, "channels.json")))
    targets = [r for r in rows
               if (r["tier"] == "A" or r.get("attribution_rate", 0) >= 0.3)
               and r["videos"] > 0]
    try:
        done = json.load(open(OUT))
    except Exception:
        done = {}

    meta = yt.channels_by_ids([r["channel_id"] for r in targets])
    today = dt.date.today()
    all_videos = []
    try:
        prev = json.load(open(VIDEOS_OUT))
        seen_ch = {v["channel_id"] for v in prev}
        all_videos = [v for v in prev if v["channel_id"] in seen_ch]
    except Exception:
        pass

    for i, r in enumerate(targets, 1):
        cid = r["channel_id"]
        if cid in done:
            continue
        if yt.quota_used() > 10000 - RESERVE:
            print("!! guard de cuota, parando en %d/%d" % (i, len(targets)))
            break
        m = meta.get(cid)
        if not m:
            continue
        try:
            ids = yt.playlist_videos(yt.uploads_playlist(m),
                                     limit=min(limit_per_channel, r["videos"]))
            recs = yt.videos(ids)
        except yt.QuotaExceeded:
            print("!! cuota agotada en %d/%d" % (i, len(targets)))
            break
        except Exception as e:
            print("   skip %s (%s)" % (r["title"][:22], str(e)[:50]))
            continue

        kept = []
        for v in recs:
            secs = scope.iso_seconds(v.get("contentDetails", {})
                                     .get("duration", ""))
            if shorts.is_short(secs, v["id"]):
                continue  # shorts and live placeholders never enter
            st = v.get("statistics", {})
            age = metrics.age_days(v["snippet"]["publishedAt"], today)
            if age is None or age < 0:
                continue
            views = int(st.get("viewCount", 0))
            mat = metrics.maturity(age)
            rec = {
                # Same record shape harvest.py produces, so the video tables can
                # be built from the full catalogue instead of a 50-video sample.
                "video_id": v["id"],
                "channel_id": cid,
                "channel_title": m["snippet"]["title"],
                "title": v["snippet"]["title"],
                "description": (v["snippet"].get("description") or "")[:1500],
                "published": v["snippet"]["publishedAt"],
                "views": views,
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "tags": v["snippet"].get("tags", [])[:25],
                "perp": round(views / mat) if mat else views,
                "age": age,
                "secs": secs,
                "duration": v.get("contentDetails", {}).get("duration", ""),
            }
            rec["handles"] = extract.handles(rec["title"])
            # Same content-space test the video tables use, so a channel can be
            # judged on whether it publishes anything relevant at all.
            extract.enrich([rec])
            rec["scope"], rec["scope_reason"] = scope.classify(rec)
            kept.append(rec)

        if not kept:
            done[cid] = {"n": 0}
            continue
        perp = [k["perp"] for k in kept]
        r90 = [k["perp"] for k in kept
               if RECENT_MIN <= k["age"] <= RECENT_MAX and k["scope"] == "in"]
        creators = {norm(h) for k in kept for h in k["handles"] if norm(h)}
        all_videos.extend(kept)
        in_scope = [k for k in kept if k["scope"] == "in"]
        done[cid] = {
            "n": len(kept),
            "n_in_scope": len(in_scope),
            "perp_median_in": (round(statistics.median([k["perp"] for k in in_scope]))
                               if in_scope else None),
            "n_reported": r["videos"],
            "shorts_excluded": r["videos"] - len(kept),
            "views": sum(k["views"] for k in kept),
            "perp_total": sum(perp),
            "perp_mean": round(statistics.mean(perp)),
            "perp_median": round(statistics.median(perp)),
            "perp_90d": round(statistics.mean(r90)) if r90 else None,
            "perp_90d_median": round(statistics.median(r90)) if r90 else None,
            "n_90d": len(r90),
            "n_90d_raw": sum(1 for k in kept if k["age"] <= RECENT_MAX),
            "recent_window": [RECENT_MIN, RECENT_MAX],
            "creators": sorted(creators),
            "attribution": round(sum(1 for k in kept if k["handles"]) / len(kept), 2),
            "median_secs": round(statistics.median([k["secs"] for k in kept])),
        }
        if i % 25 == 0:
            print("   %d/%d canales, cuota %d" % (i, len(targets), yt.quota_used()))
            json.dump(done, open(OUT, "w"), indent=1)

    shorts.save()
    # Deduplicate: a resumed run re-appends channels it re-processed.
    uniq = {v["video_id"]: v for v in all_videos}
    json.dump(list(uniq.values()), open(VIDEOS_OUT, "w"))
    json.dump(done, open(OUT, "w"), indent=1)
    ok = [d for d in done.values() if d.get("n")]
    print("\nCatálogo completo de %d canales | %s vídeos largos"
          % (len(ok), f"{sum(d['n'] for d in ok):,}"))
    print("Shorts y directos excluidos: %s"
          % f"{sum(max(0, d.get('shorts_excluded', 0)) for d in ok):,}")
    print("Vídeos guardados para las tablas: %s" % f"{len(uniq):,}")
    print("Cuota usada: %d" % yt.quota_used())
    return done


if __name__ == "__main__":
    main()
