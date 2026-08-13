"""Find false negatives: uncredited videos that are really covering a project
we already know about.

Requiring an attribution is a strict rule, and strict rules cut both ways. The
worry is a distributor that covered a great project and simply did not credit
anyone. Two independent ways to catch those:

1. Project matching. Distributors describe the same build in near-identical
   words ("Man Transforms 8 Water Tanks into Amazing Boat"). If an uncredited
   title overlaps strongly with a credited one — or with a Quantum Makers title
   — it is the same project, and the missing credit is a labelling gap rather
   than different content.

2. Reach triage. A false negative only costs us if the video did well. Sorting
   the uncredited set by projected reach turns an unbounded worry into a short
   list a human can actually read.
"""
import collections
import json
import math
import os
import re

import scope

# A compilation matching another compilation is not a lost candidate — both are
# the wrong format. Attribution does not guarantee a single project either:
# some channels credit a manufacturer on a "15 INCREDIBLE MACHINES" roundup.
COMPILATION = re.compile(
    r"^\s*\d{1,3}\s|\btop\s*\d{1,3}\b|\b\d{1,3}\s+(incredible|amazing|"
    r"insane|best|coolest|craziest|dangerous|extreme|luxurious|real|most|"
    r"inventions|gadgets|machines|vehicles|tools|ideas|things)", re.I)


def is_compilation(title):
    if COMPILATION.search(title or ""):
        return True
    return any(rx.search(title or "") for name, rx in scope.NEGATIVE
               if name in ("listicle", "gadget_roundup"))

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Words every title in this niche shares; they carry no project identity.
STOP = set("""a an the of in on at to for with and or from by his her their its
this that is are was were be been man woman men women guy couple family he she
they you your my our start finish full complete process build building builds
built make makes making made how why what when where who amazing incredible
awesome stunning beautiful perfect ultimate best top new old diy own alone
himself herself themselves day days week weeks month months year years time
video watch see look part episode ep timelapse time-lapse into out up down""".split())


def tokens(title):
    t = re.sub(r"[@#][\w.\-]+", " ", title.lower())
    t = re.sub(r"[^a-z0-9áéíóúñüçãõâêôàèìòùäöß ]", " ", t)
    words = [w for w in t.split() if len(w) > 2 and w not in STOP]
    return set(words)


IDF = {}


def build_idf(all_titles):
    """Rarity weight per word. "cabin", "forest" and "log" appear in hundreds of
    titles and identify nothing; "fv4005" or "bamboo" pin down one project."""
    df = collections.Counter()
    for t in all_titles:
        for w in tokens(t):
            df[w] += 1
    n = max(1, len(all_titles))
    IDF.clear()
    for w, c in df.items():
        IDF[w] = math.log(n / c)


def similarity(a, b):
    """Rarity-weighted containment, gated on a minimum of shared words.

    Plain containment read 1.00 whenever a short title sat inside a longer one,
    matching unrelated builds through generic vocabulary. Weighting by rarity
    means four coincidences on "cabin, cozy, forest, log" score far below four
    on "bamboo, floating, island, massive"."""
    if not a or not b:
        return 0.0
    inter = a & b
    # Scale the requirement: a title left with only three distinctive words
    # ("cabin, wood, woods") must match all three, while longer titles need
    # MIN_OVERLAP. A flat threshold discarded exact matches on short titles.
    if len(inter) < max(3, min(MIN_OVERLAP, len(a), len(b))):
        return 0.0
    num = sum(IDF.get(w, 1.0) for w in inter)
    den = min(sum(IDF.get(w, 1.0) for w in a), sum(IDF.get(w, 1.0) for w in b))
    return num / den if den else 0.0


MIN_OVERLAP = 4  # distinctive words that must coincide


def main(threshold=0.7, min_tokens=3):
    vids = json.load(open(os.path.join(DATA, "scored_videos.json")))
    qm = json.load(open(os.path.join(DATA, "qm_videos.json")))

    credited = [v for v in vids if v["scope"] == "in"]
    uncredited = [v for v in vids if v["scope"] == "out"]
    build_idf([v["title"] for v in vids] + [v["title"] for v in qm])

    # Index credited projects (ours and theirs) by token, so each uncredited
    # title is only compared against plausible candidates.
    ref = []
    for v in credited:
        ref.append((tokens(v["title"]), v, "distribuidor"))
    for v in qm:
        ref.append((tokens(v["title"]), v, "Quantum Makers"))
    index = collections.defaultdict(list)
    for i, (tok, v, src) in enumerate(ref):
        for w in tok:
            index[w].append(i)

    matches = []
    for u in uncredited:
        tu = tokens(u["title"])
        if len(tu) < min_tokens:
            continue
        cand = collections.Counter()
        for w in tu:
            for i in index.get(w, ()):
                cand[i] += 1
        best = None
        for i, _ in cand.most_common(40):
            tok, v, src = ref[i]
            if v["channel_id"] == u["channel_id"]:
                continue  # same channel re-uploading itself is not evidence
            s = similarity(tu, tok)
            if best is None or s > best[0]:
                best = (s, v, src)
        if best and best[0] >= threshold:
            s, v, src = best
            if is_compilation(u["title"]) or is_compilation(v["title"]):
                continue  # compilation ↔ compilation: not a project we lost
            creator = (v.get("source_handles_title")
                       or v.get("source_handles_desc") or [None])[0]
            matches.append({
                "overlap": sorted(tu & tokens(v["title"])),
                "video_id": u["video_id"], "title": u["title"],
                "channel": u["channel_title"],
                "perpetuity": u["perpetuity_views"], "views": u["views"],
                "age_days": u["age_days"],
                "match_score": round(s, 2),
                "match_title": v["title"], "match_channel": src if src ==
                "Quantum Makers" else v["channel_title"],
                "match_source": src,
                "creator": creator,
            })

    matches.sort(key=lambda m: -m["perpetuity"])
    json.dump(matches, open(os.path.join(DATA, "recovered.json"), "w"), indent=1)
    return matches, credited, uncredited


if __name__ == "__main__":
    m, credited, uncredited = main()
    tot_reach = sum(v["perpetuity_views"] for v in uncredited)
    rec_reach = sum(x["perpetuity"] for x in m)
    print("Sin atribución: %d vídeos" % len(uncredited))
    print("De ellos, coinciden con un proyecto ya conocido: %d (%.1f%%)"
          % (len(m), 100 * len(m) / max(1, len(uncredited))))
    print("  vía un vídeo de Quantum Makers: %d"
          % sum(1 for x in m if x["match_source"] == "Quantum Makers"))
    print("  vía otro distribuidor que sí acredita: %d"
          % sum(1 for x in m if x["match_source"] == "distribuidor"))
    print()
    print("Alcance proyectado que estaríamos perdiendo: %s de %s (%.0f%%)"
          % (f"{rec_reach:,}", f"{tot_reach:,}", 100 * rec_reach / max(1, tot_reach)))
    print()
    print("LOS 12 DE MÁS ALCANCE QUE HABRÍAMOS PERDIDO:")
    for x in m[:12]:
        print("  %11s  %-18s %s" % (f"{x['perpetuity']:,}", x["channel"][:18],
                                    x["title"][:44]))
        print("      = %s (%s) @%s  sim %.2f" % (
            x["match_title"][:44], x["match_channel"][:16],
            x["creator"] or "?", x["match_score"]))
