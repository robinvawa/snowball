"""Resolve each source creator's OWN channel.

Until now every feature described what *distributors* did with a creator's
material. Nothing described the creator. Their own channel — size, output,
average pull, age, country — is a whole feature set we never looked at, and
Quantum Makers' 182 labelled creators let us find out which of those features
actually predict a QM hit.
"""
import json
import os
import time

import yt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "creator_channels.json")


def load():
    try:
        return json.load(open(OUT))
    except Exception:
        return {}


def main(budget_reserve=250):
    rows = json.load(open(os.path.join(DATA, "creator_priority.json")))["creators"]
    known = load()
    # Labelled creators first: without them there is nothing to learn from.
    rows.sort(key=lambda r: (r["status"] != "probado_ok" and r["qm_videos"] == 0,
                             -(r["dist_best_reach"] or 0)))
    done = miss = 0
    for r in rows:
        k = r["key"]
        if k in known:
            continue
        if yt.quota_used() > 10000 - budget_reserve:
            print("!! stopping: quota guard")
            break
        try:
            it = yt.channel_by_handle(r["creator"])
        except yt.QuotaExceeded:
            print("!! quota exhausted")
            break
        except Exception:
            it = None
        if it:
            st, sn = it["statistics"], it["snippet"]
            known[k] = {
                "channel_id": it["id"],
                "title": sn["title"],
                "handle": sn.get("customUrl", ""),
                "subs": int(st.get("subscriberCount", 0)),
                "videos": int(st.get("videoCount", 0)),
                "views": int(st.get("viewCount", 0)),
                "country": sn.get("country", ""),
                "created": sn.get("publishedAt", "")[:10],
                "found": True,
            }
            done += 1
        else:
            known[k] = {"found": False}
            miss += 1
        if (done + miss) % 100 == 0:
            print("   %d resueltos, %d no encontrados, cuota %d"
                  % (done, miss, yt.quota_used()))
            json.dump(known, open(OUT, "w"), indent=1)
    json.dump(known, open(OUT, "w"), indent=1)
    ok = sum(1 for v in known.values() if v.get("found"))
    print("\nCanales de creador resueltos: %d de %d intentados (%d sin handle válido)"
          % (ok, len(known), len(known) - ok))
    print("Cuota usada: %d" % yt.quota_used())
    return known


if __name__ == "__main__":
    main()
