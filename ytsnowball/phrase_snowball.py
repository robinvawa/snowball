"""Second discovery channel: find distributors that never credit the creator.

The handle snowball can only see channels that write "by @creator" in their
titles. A manual sweep by a colleague turned up two channels we had missed —
World Tech (200k subs) and Survival Challenge (38k) — and both have 2% and 0%
attribution. They are structurally invisible to the handle method.

The fix is to search the *project* rather than the creator: take a distinctive
phrase from a title we already know, and anyone who covered the same build shows
up regardless of whether they credit anyone.
"""
import collections
import json
import os
import re

import yt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
STATE = os.path.join(DATA, "phrase_state.json")

RESERVE = 200
# Template scaffolding that carries no project information.
NOISE = re.compile(
    r"\|.*$|\bstart to finish\b|\bfrom start to finish\b|\bfull build\b|"
    r"\bbuild process\b|\btimelapse\b|\bfrom beginning to end\b|"
    r"\bstep by step\b|\bfull process\b|#\w+|[\U0001F300-\U0001FAFF☀-➿]",
    re.I)


def clean_title(t):
    t = re.sub(r"[@‪-‮⁦-⁩]\S+", " ", t)
    t = NOISE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–—|.,!?")
    return t


def known_channel_ids():
    ids = set(json.load(open(os.path.join(DATA, "seeds.json")))["seeds"])
    ids |= {c["channel_id"] for c in
            json.load(open(os.path.join(DATA, "channels.json")))}
    ids |= set(json.load(open(os.path.join(DATA, "snowball_state.json")))["hits"])
    try:
        ids |= set(json.load(open(os.path.join(DATA, "manual_list.json"))))
    except Exception:
        pass
    try:
        ids.add(json.load(open(os.path.join(DATA, "qm_channel.json")))["id"])
    except Exception:
        pass
    return ids


def pick_phrases(n=30):
    """Distinctive titles of projects that demonstrably travel: the ones with
    the biggest reach, since those are what other channels re-edit."""
    vids = json.load(open(os.path.join(DATA, "scored_videos.json")))
    try:
        vids += json.load(open(os.path.join(DATA, "qm_videos.json")))
    except Exception:
        pass
    vids = [v for v in vids if v.get("scope") != "out"]
    vids.sort(key=lambda v: -v.get("perpetuity_views", 0))
    out, seen = [], set()
    for v in vids:
        p = clean_title(v["title"])
        if len(p.split()) < 5 or len(p) > 110:
            continue
        key = " ".join(sorted(p.lower().split())[:6])
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= n:
            break
    return out


def run(max_searches=25):
    try:
        state = json.load(open(STATE))
    except Exception:
        state = {"searched": [], "hits": {}}
    searched = set(state["searched"])
    hits = state["hits"]
    known = known_channel_ids()

    done = 0
    for phrase in pick_phrases(120):
        if done >= max_searches:
            break
        if phrase in searched:
            continue
        if yt.quota_used() > 10000 - RESERVE - 100:
            print("!! guard de cuota")
            break
        try:
            items = yt.search('"%s"' % phrase[:70], max_results=25)
        except yt.QuotaExceeded:
            print("!! cuota de búsqueda agotada")
            break
        done += 1
        searched.add(phrase)
        fresh = 0
        for it in items:
            sn = it["snippet"]
            cid = sn["channelId"]
            if cid in known:
                continue
            rec = hits.setdefault(cid, {"title": sn["channelTitle"],
                                        "phrases": [], "examples": []})
            if phrase not in rec["phrases"]:
                rec["phrases"].append(phrase)
                fresh += 1
            if len(rec["examples"]) < 3:
                rec["examples"].append({"video_id": it["id"]["videoId"],
                                        "title": sn["title"]})
        print("  [%2d] %-58s -> %2d nuevos (cuota %d)"
              % (done, phrase[:58], fresh, yt.quota_used()))

    json.dump({"searched": sorted(searched), "hits": hits},
              open(STATE, "w"), indent=1)
    print("\nBúsquedas: %d | canales desconocidos vistos: %d" % (done, len(hits)))
    multi = {k: v for k, v in hits.items() if len(v["phrases"]) >= 2}
    print("De ellos, cubren 2+ proyectos nuestros (= distribuidor casi seguro): %d"
          % len(multi))
    return hits, multi


if __name__ == "__main__":
    run()
