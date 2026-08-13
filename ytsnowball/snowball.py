"""Snowball: search each source-creator handle, collect the channels that
covered it. A channel covering 2+ pool creators is a distributor."""
import collections
import json
import os
import re
import sys

import extract
import yt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Our own channel must never end up in the distributor list.
OWN = {"quantum makers", "quantummakers"}

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


def run(videos, max_searches=40):
    state_path = os.path.join(DATA, "snowball_state.json")
    try:
        state = json.load(open(state_path))
    except Exception:
        state = {"searched": [], "hits": {}}
    searched = set(state["searched"])
    hits = collections.defaultdict(dict)
    for cid, rec in state["hits"].items():
        hits[cid] = rec

    todo = rank_creators(videos, searched)
    print("Candidate source creators not yet searched: %d" % len(todo))

    done = 0
    for key, handle, ncov, outlier in todo:
        if done >= max_searches:
            break
        if yt.quota_used() > DAILY_QUOTA - RESERVE - 100:
            print("\n!! Quota guard hit, stopping searches.")
            break
        try:
            items = yt.search('"%s"' % handle, max_results=50)
        except yt.QuotaExceeded:
            print("\n!! API reports quota exhausted.")
            break
        done += 1
        searched.add(key)
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

    state = {"searched": sorted(searched), "hits": dict(hits)}
    json.dump(state, open(state_path, "w"), indent=1)
    print("\nSearches this run: %d | quota used today: %d" % (done, yt.quota_used()))
    print("Channels seen: %d" % len(hits))
    return state


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    vids = json.load(open(os.path.join(DATA, "seed_videos.json")))
    disc = os.path.join(DATA, "discovered_videos.json")
    if os.path.exists(disc):  # iteration 2+: rank over the expanded pool
        vids += json.load(open(disc))
    vids = extract.enrich(vids)
    run(vids, max_searches=n)
