"""Rank source creators by the odds they have at least one top project.

Two design decisions drive this, both learned the hard way:

1. THE MAXIMUM IS THE TARGET, NOT THE MEAN. We only need one top project from a
   creator. A creator with one enormous hit and six flops HAS a top project —
   that is a demonstrated fact, not an estimate, and averaging it away is the
   wrong operation. So the score is driven by the best reading, and non-hits
   never subtract from it. They only fail to add.

2. AN OUTLIER ON A SMALL CHANNEL IS WORTH LESS. A x400 that reached 800 people
   is a statistical artifact of a tiny, unstable baseline; a x5 that reached
   3.5M is a real result. So a reading only counts as strong when it clears BOTH
   bars — relative pull against its own channel AND absolute reach. Taking the
   min of the two percentiles means neither alone is enough.

   Measured, not assumed: within-channel dispersion of log-outlier turns out to
   be flat across channel sizes (~0.67-0.80 sd everywhere), so normalising by
   channel volatility does nothing. What does separate them is predictive value
   — readings from sub-10k channels correlate 0.030 with the rest of that
   creator's readings, versus 0.120 for 10k-100k channels. Reach is the variable
   that carries that credibility, so reach is what we gate on.
"""
import collections
import json
import math
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

STRONG = 0.60        # percentile bar for "this reading demonstrates a top project"
DOUBT_DECAY = 0.60   # each independent confirmation removes 40% of remaining doubt
FLOOR = 0.02


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def pct_ranks(values):
    """Percentile rank in [0,1]; ties share a rank."""
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


def gather():
    vids = [v for v in json.load(open(os.path.join(DATA, "scored_videos.json")))
            if v["scope"] != "out" and v["source_handles_title"]]
    by, label = collections.defaultdict(dict), {}
    for v in vids:
        for h in v["source_handles_title"]:
            k = norm(h)
            if not k:
                continue
            label.setdefault(k, h)
            # One reading per distributor: their best shot at this creator.
            cur = by[k].get(v["channel_id"])
            if cur is None or v["perp_outlier"] > cur["perp_outlier"]:
                by[k][v["channel_id"]] = v
    return by, label


def build():
    by, label = gather()

    readings = [(k, v) for k, d in by.items() for v in d.values()]
    rel = pct_ranks([math.log10(max(v["perp_outlier"], FLOOR)) for _, v in readings])
    rch = pct_ranks([math.log10(max(v["perpetuity_views"], 1)) for _, v in readings])

    strength = collections.defaultdict(list)
    for i, (k, v) in enumerate(readings):
        # Both bars, or it does not count. This is the small-channel adjustment.
        s = min(rel[i], rch[i])
        strength[k].append((s, v, rel[i], rch[i]))

    subs = {c["channel_id"]: c["subs"]
            for c in json.load(open(os.path.join(DATA, "channels.json")))}

    recs = []
    for k, items in strength.items():
        items.sort(key=lambda t: -t[0])
        s_max, best, best_rel, best_rch = items[0]
        confirms = [t for t in items[1:] if t[0] >= STRONG]

        # Residual doubt shrinks with each *independent* confirmation. Readings
        # that did not hit are simply ignored — they never push the score down.
        odds = 1.0 - (1.0 - s_max) * (DOUBT_DECAY ** len(confirms))

        recs.append({
            "key": k, "creator": label[k],
            "url": "https://www.youtube.com/@%s" % label[k],
            "distributors": len(items),
            "odds_top": round(odds, 4),
            "best_strength": round(s_max, 3),
            "confirmations": len(confirms),
            "strong_readings": sum(1 for t in items if t[0] >= STRONG),
            "best_outlier": round(best["perp_outlier"], 1),
            "best_reach": best["perpetuity_views"],
            "best_rel_pct": round(best_rel, 3),
            "best_reach_pct": round(best_rch, 3),
            "best_title": best["title"],
            "best_video": best["video_id"],
            "best_channel": best["channel_title"],
            "best_channel_subs": subs.get(best["channel_id"], 0),
            "peak_outlier_any": round(max(t[1]["perp_outlier"] for t in items), 1),
            "peak_reach_any": max(t[1]["perpetuity_views"] for t in items),
            "last_seen": max(t[1]["published"] for t in items)[:10],
            "evidence": ("firme" if len(confirms) >= 1 else
                         "media" if len(items) >= 3 else "débil"),
        })

    # Our own channel shows up as a "source creator" because 7 distributors
    # re-edit us. It belongs in the brand alert, not in a sourcing shortlist.
    recs = [r for r in recs if r["key"] != "quantummakers"]

    recs.sort(key=lambda r: (-r["odds_top"], -r["best_reach"]))
    json.dump({"params": {"strong": STRONG, "doubt_decay": DOUBT_DECAY},
               "creators": recs},
              open(os.path.join(DATA, "creator_odds.json"), "w"), indent=1)
    return recs


if __name__ == "__main__":
    recs = build()
    print("Creadores puntuados: %d" % len(recs))
    for lo, hi in ((.9, 1.01), (.75, .9), (.6, .75), (.4, .6), (0, .4)):
        print("  odds %2.0f-%3.0f%%: %3d" % (100 * lo, 100 * hi,
              sum(1 for r in recs if lo <= r["odds_top"] < hi)))
    print()
    print("%-24s %5s %6s %5s %8s %10s %-7s %s" %
          ("CREADOR", "ODDS", "fuerza", "conf", "outlier", "alcance",
           "evid", "mejor proyecto"))
    for r in recs[:18]:
        print("%-24s %4.0f%% %6.2f %4d %8s %10s %-7s %s" % (
            r["creator"][:24], 100 * r["odds_top"], r["best_strength"],
            r["confirmations"], "x%.0f" % r["best_outlier"],
            f"{r['best_reach']:,}", r["evidence"], r["best_title"][:34]))

    print()
    print("--- comprobación: creadores de 1 pico enorme + fracasos ---")
    solo = [r for r in recs if r["distributors"] >= 5 and r["confirmations"] == 0
            and r["best_strength"] >= 0.75]
    for r in solo[:6]:
        print("  %-22s odds %2.0f%%  1 de %d lecturas fuerte, resto flojas, x%.0f / %s views"
              % (r["creator"][:22], 100 * r["odds_top"], r["distributors"],
                 r["best_outlier"], f"{r['best_reach']:,}"))
