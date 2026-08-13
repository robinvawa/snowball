"""Fold Quantum Makers' own history into the creator ranking.

Measured on QM's own catalogue (82 creators with 2+ QM videos):

    first QM video was an outlier  -> 58% chance of another outlier later
    first QM video was not         -> 27%

So QM's own track record on a creator is a stronger predictor of future QM
success than anything the distributors provide (r~0.25). That splits creators
into three genuinely different situations, which is what this module produces.
"""
import collections
import json
import math
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

QM_HIT = 2.0        # x2 over QM's own median = an outlier for them
P_REPEAT_HIT = 0.58  # measured
P_REPEAT_MISS = 0.27  # measured


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_qm():
    qm = json.load(open(os.path.join(DATA, "qm_videos.json")))
    by = collections.defaultdict(list)
    for v in qm:
        for h in v["source_handles_title"]:
            k = norm(h)
            if k:
                by[k].append(v)
    return qm, by


def calibrate(odds, qm_by):
    """Fit log-odds of a QM hit on the distributor strength, over the creators
    where both exist. Contaminated (QM published first in 88% of them), so this
    is a calibration aid, not a causal claim."""
    xs, ys = [], []
    for k, c in odds.items():
        if k in qm_by:
            xs.append(c["best_strength"])
            ys.append(1.0 if max(v["perp_outlier"] for v in qm_by[k]) >= QM_HIT
                      else 0.0)
    if len(xs) < 20:
        return None
    # Single-feature logistic by gradient ascent; tiny problem, no deps needed.
    b0, b1 = 0.0, 0.0
    for _ in range(4000):
        g0 = g1 = 0.0
        for x, y in zip(xs, ys):
            p = 1 / (1 + math.exp(-(b0 + b1 * x)))
            g0 += y - p
            g1 += (y - p) * x
        b0 += 0.05 * g0 / len(xs)
        b1 += 0.05 * g1 / len(xs)
    return b0, b1, statistics.mean(ys)


def load_model():
    try:
        return json.load(open(os.path.join(DATA, "creator_model.json")))
    except Exception:
        return None


def build():
    qm, qm_by = load_qm()
    mdl = load_model()
    mscore = (mdl or {}).get("scores", {})
    data = json.load(open(os.path.join(DATA, "creator_odds.json")))
    odds = {c["key"]: c for c in data["creators"]}

    cal = calibrate(odds, qm_by)
    b0, b1, base = cal if cal else (0.0, 0.0, 0.3)

    rows = []
    keys = set(odds) | set(qm_by)
    for k in keys:
        c = odds.get(k)
        qv = sorted(qm_by.get(k, []), key=lambda v: v["published"])
        rec = {
            "key": k,
            "creator": (c["creator"] if c else
                        (qv[0]["source_handles_title"] or [k])[0]),
            "qm_videos": len(qv),
            "qm_best_outlier": round(max((v["perp_outlier"] for v in qv),
                                         default=0), 2),
            "qm_best_views": max((v["perpetuity_views"] for v in qv), default=0),
            "qm_best_title": (max(qv, key=lambda v: v["perp_outlier"])["title"]
                              if qv else ""),
            "qm_best_video": (max(qv, key=lambda v: v["perp_outlier"])["video_id"]
                              if qv else ""),
            "qm_last": max((v["published"][:10] for v in qv), default=""),
            "distributors": c["distributors"] if c else 0,
            "dist_odds": c["odds_top"] if c else None,
            "dist_strength": c["best_strength"] if c else None,
            "dist_best_outlier": c["best_outlier"] if c else None,
            "dist_best_reach": c["best_reach"] if c else None,
            "dist_best_title": c["best_title"] if c else "",
            "dist_best_video": c["best_video"] if c else "",
            "dist_best_channel": c["best_channel"] if c else "",
            "confirmations": c["confirmations"] if c else 0,
            "model_score": mscore.get(k),
            "url": "https://www.youtube.com/@%s" % (
                c["creator"] if c else (qv[0]["source_handles_title"] or [k])[0]),
        }

        if qv:
            hit = rec["qm_best_outlier"] >= QM_HIT
            rec["status"] = "probado_ok" if hit else "probado_flojo"
            rec["p_next"] = P_REPEAT_HIT if hit else P_REPEAT_MISS
            rec["why"] = ("ya os funcionó — su catálogo es mina" if hit
                          else "ya probado, no despegó")
        else:
            rec["status"] = "sin_explorar"
            # Model trained on QM's own labels; falls back to the single-feature
            # calibration when we could not resolve the creator's channel.
            if k in mscore:
                rec["p_next"] = mscore[k]
                rec["why"] = "sin explorar — predicción del modelo"
            else:
                s = rec["dist_strength"] or 0.0
                rec["p_next"] = 1 / (1 + math.exp(-(b0 + b1 * s)))
                rec["why"] = "sin explorar — sin canal resuelto"

        rows.append(rec)

    # Rank: probability of a hit first, then how big the demonstrated ceiling is.
    rows.sort(key=lambda r: (-r["p_next"],
                             -(r["qm_best_views"] or r["dist_best_reach"] or 0)))
    json.dump({"params": {"qm_hit": QM_HIT, "b0": b0, "b1": b1,
                          "base_rate": base,
                          "p_repeat_hit": P_REPEAT_HIT,
                          "p_repeat_miss": P_REPEAT_MISS},
               "creators": rows},
              open(os.path.join(DATA, "creator_priority.json"), "w"), indent=1)
    return rows, (b0, b1, base)


if __name__ == "__main__":
    rows, (b0, b1, base) = build()
    cnt = collections.Counter(r["status"] for r in rows)
    print("Creadores totales: %d" % len(rows))
    for s in ("probado_ok", "probado_flojo", "sin_explorar"):
        print("  %-14s %d" % (s, cnt[s]))
    print()
    print("Calibración logística sobre los solapados:")
    print("  b0=%.2f b1=%.2f | tasa base de acierto de QM en solapados: %.0f%%"
          % (b0, b1, 100 * base))
    print("  fuerza 0.2 -> %.0f%% | fuerza 0.6 -> %.0f%% | fuerza 0.95 -> %.0f%%"
          % tuple(100 / (1 + math.exp(-(b0 + b1 * s))) for s in (.2, .6, .95)))
    print()
    mina = [r for r in rows if r["status"] == "probado_ok"]
    mina.sort(key=lambda r: -r["qm_best_views"])
    print("MINA: creadores que YA os funcionaron (58%% de otro acierto) — top 10")
    for r in mina[:10]:
        print("  %-24s vuestro x%-5.1f %12s views  %d vídeos vuestros" % (
            r["creator"][:24], r["qm_best_outlier"],
            f"{r['qm_best_views']:,}", r["qm_videos"]))
    print()
    sin = [r for r in rows if r["status"] == "sin_explorar"
           and r["dist_best_reach"]]
    sin.sort(key=lambda r: (-r["p_next"], -r["dist_best_reach"]))
    print("SIN EXPLORAR: mejores según distribuidores — top 10")
    for r in sin[:10]:
        print("  %-24s p=%2.0f%%  dist x%-6.0f %10s en %s" % (
            r["creator"][:24], 100 * r["p_next"], r["dist_best_outlier"],
            f"{r['dist_best_reach']:,}", r["dist_best_channel"][:18]))
