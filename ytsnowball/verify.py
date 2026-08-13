"""Harvest each discovered channel's own uploads to (a) confirm it really is a
distributor and (b) expand the source-creator pool for the next iteration."""
import json
import os
import re
import sys

import extract
import harvest
import yt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BRAND = re.compile(r"quantum\s*(makers?|markers?|build)", re.I)


def main(tiers=("A", "B"), limit=50):
    rows = json.load(open(os.path.join(DATA, "channels.json")))
    targets = [r for r in rows if r["tier"] in tiers and r["videos"] > 0]
    meta = yt.channels_by_ids([r["channel_id"] for r in targets])

    allv = []
    for i, r in enumerate(targets, 1):
        m = meta.get(r["channel_id"])
        if not m:
            continue
        try:
            vids = harvest.harvest_channel(
                {"uploads_playlist": yt.uploads_playlist(m),
                 "videos": r["videos"]}, limit=limit)
        except yt.QuotaExceeded:
            print("!! quota exhausted at channel %d" % i)
            break
        except Exception as e:
            print("   skip %s (%s)" % (r["title"][:24], str(e)[:60]))
            continue
        vids = extract.enrich(vids)
        allv.extend(vids)
        n_attr = sum(1 for v in vids if v["source_handles_title"])
        r["harvested"] = len(vids)
        r["attribution_rate"] = round(n_attr / len(vids), 2) if vids else 0
        r["median_views"] = vids[0]["channel_median_views"] if vids else 0
        r["brand_lookalike"] = bool(BRAND.search(r["title"]))
        if i % 25 == 0:
            print("   ... %d/%d channels, %d videos, quota %d"
                  % (i, len(targets), len(allv), yt.quota_used()))

    json.dump(allv, open(os.path.join(DATA, "discovered_videos.json"), "w"),
              indent=1)
    json.dump(rows, open(os.path.join(DATA, "channels.json"), "w"), indent=1)
    print("\nHarvested %d videos from %d channels. Quota used: %d"
          % (len(allv), len(targets), yt.quota_used()))

    # Confirmation check: real distributors credit a source creator in the
    # title on a large share of their uploads.
    conf = [r for r in targets if r.get("attribution_rate", 0) >= 0.3]
    print("Channels with >=30%% of titles crediting a source creator: %d/%d"
          % (len(conf), len(targets)))
    return allv


if __name__ == "__main__":
    tiers = tuple(sys.argv[1]) if len(sys.argv) > 1 else ("A", "B")
    main(tiers=tiers)
