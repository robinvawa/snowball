"""Resolve creator credits hidden in video descriptions.

2,392 of the 3,690 in-scope videos credit the creator in the title; another
959 credit ONLY in the description, and the pipeline ignored those entirely —
38.6M attributable views were sitting orphaned. This module resolves them.

A description carries a median of 2 handles (max 20): the distributor's own
socials, sponsors, music, sometimes several creators. So resolution is tiered,
strongest evidence first, and anything genuinely ambiguous is left for a human
rather than guessed:

  pool   the handle is already a known source creator elsewhere in the pool.
  kw     an unknown handle sitting next to a credit word (credit / original /
         source / courtesy / video by / footage) — accepted as a NEW creator.
  unico  exactly one plausible candidate left after discarding the channel's
         own handles and other distributors. Weakest tier, marked as such.

@quantummakers in a description is not sourcing — it is a distributor
re-editing Quantum Makers itself. Those are reported separately (brand watch).

Outputs data/resolved_credits.json and data/ambiguous_credits.json, and
apply() injects resolved handles into the in-memory video list + rewrites
scored_videos.json so the whole pipeline (ranking, tabs, deltas) picks the
credit up with provenance in v["credit_src"].
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

KW = re.compile(r"(credit|original|source|courtesy|video by|footage|creator)",
                re.I)
KW_NEAR = 90   # chars around the handle where a credit word counts


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _known_sets():
    chans = json.load(open(os.path.join(DATA, "channels.json")))
    own = {norm(c.get("handle")) for c in chans} | \
          {norm(c.get("title")) for c in chans}
    own.discard("")
    pool = {c["key"] for c in
            json.load(open(os.path.join(DATA,
                                        "creator_odds.json")))["creators"]}
    return own, pool


def resolve(vids):
    own, pool = _known_sets()

    # Boilerplate del canal: un handle NO-pool que aparece en 5+ descripciones
    # del mismo canal y en 25%+ de sus vídeos con handles es plantilla (marca
    # hermana, redes propias, música), no un crédito por vídeo. Caza casos
    # como @GearForgeHD en 65 descripciones de Gear Tech HD.
    per_ch = {}
    for v in vids:
        if v.get("scope") == "out":
            continue
        ks = {norm(h) for h in (v.get("source_handles_desc") or [])} - {""}
        if ks:
            per_ch.setdefault(v["channel_id"], []).append(ks)
    boiler = set()
    for cid, sets in per_ch.items():
        n = len(sets)
        cnt = {}
        for ks in sets:
            for k in ks:
                cnt[k] = cnt.get(k, 0) + 1
        for k, c in cnt.items():
            if k not in pool and c >= 5 and c / n >= 0.25:
                boiler.add((cid, k))

    resolved, ambiguous, marca = {}, [], []
    for v in vids:
        if v.get("scope") == "out" or v.get("source_handles_title"):
            continue
        raw = v.get("source_handles_desc") or []
        seen, cands = set(), []
        for h in raw:
            k = norm(h)
            if k and k not in seen:
                seen.add(k)
                cands.append((k, h))
        if any(k == "quantummakers" for k, _ in cands):
            marca.append(v["video_id"])
        cands = [(k, h) for k, h in cands
                 if k not in own and k != "quantummakers"
                 and (v["channel_id"], k) not in boiler]
        if not cands:
            continue

        in_pool = [(k, h) for k, h in cands if k in pool]
        if len(in_pool) == 1:
            k, h = in_pool[0]
            resolved[v["video_id"]] = {"handle": h, "tier": "pool"}
            continue
        if len(in_pool) > 1:
            ambiguous.append({"video_id": v["video_id"], "title": v["title"],
                              "channel": v["channel_title"],
                              "why": "varios del pool",
                              "candidates": [h for _, h in in_pool]})
            continue

        desc = v.get("description") or ""
        near_kw = []
        for k, h in cands:
            for m in re.finditer(re.escape(h), desc, re.I):
                lo = max(0, m.start() - KW_NEAR)
                if KW.search(desc[lo:m.end() + KW_NEAR]):
                    near_kw.append((k, h))
                    break
        if len(near_kw) == 1:
            k, h = near_kw[0]
            resolved[v["video_id"]] = {"handle": h, "tier": "kw"}
            continue
        if len(near_kw) > 1:
            ambiguous.append({"video_id": v["video_id"], "title": v["title"],
                              "channel": v["channel_title"],
                              "why": "varios con palabra de crédito",
                              "candidates": [h for _, h in near_kw]})
            continue

        if len(cands) == 1:
            k, h = cands[0]
            resolved[v["video_id"]] = {"handle": h, "tier": "unico"}
        else:
            ambiguous.append({"video_id": v["video_id"], "title": v["title"],
                              "channel": v["channel_title"],
                              "why": "varios sin señal",
                              "candidates": [h for _, h in cands][:8]})
    return resolved, ambiguous, marca


def apply(vids):
    """Inject resolved credits into the video list and persist everything."""
    resolved, ambiguous, marca = resolve(vids)
    for v in vids:
        r = resolved.get(v["video_id"])
        if r and not v.get("source_handles_title"):
            v["source_handles_title"] = [r["handle"]]
            v["source_handle"] = r["handle"]
            v["credit_src"] = "desc-" + r["tier"]
    json.dump(resolved, open(os.path.join(DATA, "resolved_credits.json"), "w"),
              indent=1, ensure_ascii=False)
    json.dump(ambiguous,
              open(os.path.join(DATA, "ambiguous_credits.json"), "w"),
              indent=1, ensure_ascii=False)
    json.dump(vids, open(os.path.join(DATA, "scored_videos.json"), "w"),
              indent=1)
    return resolved, ambiguous, marca


if __name__ == "__main__":
    vids = json.load(open(os.path.join(DATA, "scored_videos.json")))
    resolved, ambiguous, marca = resolve(vids)
    import collections
    t = collections.Counter(r["tier"] for r in resolved.values())
    print("Resueltos: %d  (pool %d | palabra de crédito %d | único %d)"
          % (len(resolved), t["pool"], t["kw"], t["unico"]))
    print("Ambiguos: %d | Reeditan a Quantum Makers: %d"
          % (len(ambiguous), len(marca)))
