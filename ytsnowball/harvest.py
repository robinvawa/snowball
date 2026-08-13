"""Pull recent uploads for a set of channels and score each video against its
own channel's median. Outlier multiplier, not raw views, is the signal.

Shorts are dropped here, at ingestion, rather than filtered downstream. They are
a different format with a different view distribution, and leaving them in the
set corrupts the channel median that every outlier is measured against — on the
worst-affected channels the median came out 2.4x too low, inflating every
outlier by the same factor. As far as the rest of this project is concerned,
videos under three minutes do not exist.
"""
import json
import os
import statistics

import scope
import shorts
import yt

HERE = os.path.dirname(os.path.abspath(__file__))


def harvest_channel(ch, limit=50):
    """Return video records for one channel, each with an outlier multiplier."""
    if not ch.get("uploads_playlist") or ch.get("videos", 0) == 0:
        return []
    vids = yt.playlist_videos(ch["uploads_playlist"], limit=limit)
    if not vids:
        return []
    recs = yt.videos(vids)
    out = []
    for v in recs:
        st = v.get("statistics", {})
        dur = v.get("contentDetails", {}).get("duration", "")
        secs = scope.iso_seconds(dur)
        # Shorts (now up to 3 minutes, sometimes 181s after encoding) and live
        # placeholders ("P0D") never enter the dataset.
        if shorts.is_short(secs, v["id"]):
            continue
        out.append({
            "video_id": v["id"],
            "channel_id": v["snippet"]["channelId"],
            "channel_title": v["snippet"]["channelTitle"],
            "title": v["snippet"]["title"],
            "description": (v["snippet"].get("description") or "")[:1500],
            "published": v["snippet"]["publishedAt"],
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "duration": dur,
            "seconds": secs,
            "tags": v["snippet"].get("tags", [])[:25],
        })
    # Median over the channel's own recent output = its baseline.
    views = [v["views"] for v in out if v["views"] > 0]
    med = statistics.median(views) if views else 0
    for v in out:
        v["channel_median_views"] = med
        v["outlier"] = round(v["views"] / med, 2) if med else 0.0
    return out


def main(limit=50):
    seeds = json.load(open(os.path.join(HERE, "data", "seeds.json")))["seeds"]
    allv, per_channel = [], {}
    for cid, ch in seeds.items():
        vids = harvest_channel(ch, limit=limit)
        per_channel[cid] = len(vids)
        allv.extend(vids)
        print("  %-22s %3d videos  median %8s views" % (
            ch["title"][:22], len(vids),
            vids[0]["channel_median_views"] if vids else "-"))
    path = os.path.join(HERE, "data", "seed_videos.json")
    json.dump(allv, open(path, "w"), indent=1)
    print("\n%d videos from %d channels -> %s" % (
        len(allv), sum(1 for n in per_channel.values() if n), path))
    print("Quota used today: %d units." % yt.quota_used())
    return allv


if __name__ == "__main__":
    main()
