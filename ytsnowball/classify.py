"""Enrich discovered channels with stats and classify distributor confidence."""
import json
import os
import re

import yt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def build():
    state = json.load(open(os.path.join(DATA, "snowball_state.json")))
    seeds = json.load(open(os.path.join(DATA, "seeds.json")))["seeds"]
    hits = state["hits"]

    meta = yt.channels_by_ids(list(hits))
    rows = []
    for cid, rec in hits.items():
        m = meta.get(cid)
        if not m:
            continue  # channel deleted or terminated since the search
        st = m["statistics"]
        sn = m["snippet"]
        subs = int(st.get("subscriberCount", 0))
        vc = int(st.get("videoCount", 0))
        vw = int(st.get("viewCount", 0))
        ncre = len(rec["creators"])

        # Confidence: covering several distinct pool creators with the
        # "by @creator" attribution pattern is what defines a distributor.
        if ncre >= 3:
            tier, why = "A", "covers %d pool creators" % ncre
        elif ncre == 2:
            tier, why = "A", "covers 2 pool creators"
        elif vc and subs:
            tier, why = "B", "1 pool creator, active channel"
        else:
            tier, why = "C", "1 pool creator, thin channel"

        rows.append({
            "channel_id": cid,
            "title": sn["title"],
            "handle": sn.get("customUrl", ""),
            "url": "https://www.youtube.com/%s" % (sn.get("customUrl") or
                                                  "channel/" + cid),
            "subs": subs,
            "videos": vc,
            "total_views": vw,
            "avg_views": round(vw / vc) if vc else 0,
            "country": sn.get("country", ""),
            "published": sn.get("publishedAt", "")[:10],
            "creators_covered": ncre,
            "creators": rec["creators"],
            "tier": tier,
            "why": why,
            "is_seed": cid in seeds,
            "examples": rec["examples"],
        })

    rows.sort(key=lambda r: (-r["creators_covered"], -r["subs"]))
    json.dump(rows, open(os.path.join(DATA, "channels.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    rows = build()
    a = [r for r in rows if r["tier"] == "A"]
    b = [r for r in rows if r["tier"] == "B"]
    c = [r for r in rows if r["tier"] == "C"]
    print("Discovered channels: %d  (A=%d confirmed, B=%d likely, C=%d weak)"
          % (len(rows), len(a), len(b), len(c)))
    print("Already known as seeds: %d\n"
          % sum(1 for r in rows if r["is_seed"]))
    print("%-28s %-22s %8s %6s %10s %4s %s" %
          ("CHANNEL", "HANDLE", "SUBS", "VIDS", "AVG VIEWS", "CRE", ""))
    for r in a:
        print("%-28s %-22s %8s %6s %10s %4d %s" % (
            r["title"][:28], r["handle"][:22], f"{r['subs']:,}", r["videos"],
            f"{r['avg_views']:,}", r["creators_covered"],
            "<-- SEED" if r["is_seed"] else ""))
    print("\nQuota used today: %d" % yt.quota_used())
