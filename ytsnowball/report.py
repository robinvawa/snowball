"""Final deliverables: distributor list, source-creator pool, brand flags."""
import collections
import csv
import json
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "out")
BRAND = re.compile(r"quantum|q\s*makers", re.I)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load():
    rows = json.load(open(os.path.join(DATA, "channels.json")))
    vids = json.load(open(os.path.join(DATA, "seed_videos.json")))
    vids += json.load(open(os.path.join(DATA, "discovered_videos.json")))
    return rows, vids


def distributors(rows):
    """Tier A, plus Tier B channels whose own uploads show the attribution
    pattern. Excludes our own channel."""
    out = []
    for r in rows:
        if norm(r["title"]) in ("quantummakers",):
            continue
        strong = r["tier"] == "A" or r.get("attribution_rate", 0) >= 0.3
        if not strong:
            continue
        r["brand_lookalike"] = bool(BRAND.search(r["title"]))
        out.append(r)
    out.sort(key=lambda r: (-r["creators_covered"], -r["subs"]))
    return out


def creator_pool(vids):
    """Source creators ranked by how many distributors covered them and how
    well those uploads performed relative to each distributor's own baseline."""
    cov = collections.defaultdict(set)
    outl = collections.defaultdict(list)
    label = {}
    for v in vids:
        for h in v["source_handles_title"]:
            k = norm(h)
            if not k:
                continue
            cov[k].add(v["channel_id"])
            if v.get("outlier"):
                outl[k].append(v["outlier"])
            label.setdefault(k, h)
    pool = []
    for k, chans in cov.items():
        os_ = outl[k] or [0]
        pool.append({
            "creator": label[k],
            "url": "https://www.youtube.com/@%s" % label[k],
            "distributors": len(chans),
            "uploads": len(os_),
            "median_outlier": round(statistics.median(os_), 2),
            "max_outlier": round(max(os_), 2),
        })
    pool.sort(key=lambda p: (-p["distributors"], -p["max_outlier"]))
    return pool


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, vids = load()
    dist = distributors(rows)
    pool = creator_pool(vids)

    cols = ["title", "handle", "url", "subs", "videos", "avg_views",
            "median_views", "creators_covered", "attribution_rate", "country",
            "published", "tier", "is_seed", "brand_lookalike", "channel_id"]
    with open(os.path.join(OUT, "distributors.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in dist:
            w.writerow(r)

    with open(os.path.join(OUT, "source_creators.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pool[0]))
        w.writeheader()
        w.writerows(pool)

    ours = [p for p in pool if norm(p["creator"]) == "quantummakers"]
    looks = [r for r in dist if r["brand_lookalike"]]

    print("=" * 68)
    print("DISTRIBUTOR CHANNELS: %d" % len(dist))
    print("  new (not in your original list): %d"
          % sum(1 for r in dist if not r["is_seed"]))
    print("  combined subscribers: %s" % f"{sum(r['subs'] for r in dist):,}")
    print("  >100k subs: %d | 10k-100k: %d | <10k: %d" % (
        sum(1 for r in dist if r["subs"] >= 100000),
        sum(1 for r in dist if 10000 <= r["subs"] < 100000),
        sum(1 for r in dist if r["subs"] < 10000)))
    print("\nSOURCE CREATORS TRACKED: %d" % len(pool))
    print("  covered by 3+ distributors: %d"
          % sum(1 for p in pool if p["distributors"] >= 3))
    print("\nBRAND LOOKALIKES: %d" % len(looks))
    for r in looks:
        print("  %-26s %-24s %8s subs" % (r["title"][:26], r["handle"][:24],
                                          f"{r['subs']:,}"))
    if ours:
        print("\nDistributors crediting @QuantumMakers: %d"
              % ours[0]["distributors"])
    print("\nWrote out/distributors.csv and out/source_creators.csv")
    return dist, pool


if __name__ == "__main__":
    main()
