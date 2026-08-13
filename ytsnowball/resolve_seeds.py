"""Resolve the messy seed list into canonical channel IDs."""
import itertools
import json
import os
import re

import yt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "seeds.json")

# As supplied, with the concatenated-URL damage stripped out.
RAW = [
    ("TechFreeze", "handle", "@TechFreeze"),
    ("Makerium", "handle", "@Makerium"),
    ("Lord Gizmo", "handle", "@LordGizmo"),
    ("AKLA GELEN", "handle", "@AKLAGELEN"),
    ("22TechZoom", "handle", "@22TechZoom"),
    ("WildCraft Builds", "handle", "@WildCraftBuilds"),
    ("populerwrldvideo", "handle", "@populerwrldvideo"),
    ("Makerworld-official", "handle", "@Makerworld-official"),
    ("NovaCraftSTDv", "handle", "@NovaCraftSTDv"),
    ("Machinestage", "handle", "@Machinestage"),
    # Añadidos tras la revisión manual (ago 2026). Los dos primeros no
    # acreditan al creador (2 % y 0 %), así que el snowball de handles no
    # podía verlos; Living Ideas sí acredita, pero sus creadores estaban
    # entre los ~620 que quedaron sin buscar por cuota.
    ("World Tech (real)", "handle", "@worldtechyt"),
    ("Survival Challenge", "handle", "@survivalchallenge.2023"),
    ("Living Ideas", "handle", "@livingideas-t6e"),
    ("(video 5px-Rz5V3aw)", "video", "5px-Rz5V3aw"),
    ("(video BoBALDJmFjc)", "video", "BoBALDJmFjc"),
]


def handle_variants(name):
    """Cheap guesses (1 unit each) before falling back to search (100)."""
    base = name.lstrip("@")
    words = re.findall(r"[A-Za-z0-9]+", base)
    cands = [base, base.replace(" ", ""), base.replace(" ", "-"),
             base.replace(" ", "_"), "".join(words), "".join(words).lower(),
             "".join(w.capitalize() for w in words)]
    # Common suffixes these channels use when the bare handle is taken.
    for suf in ("official", "tv", "yt", "1", "official1"):
        cands.append("".join(words) + suf)
    return list(dict.fromkeys(c for c in cands if c))


def resolve():
    seeds, unresolved = {}, []
    for label, kind, value in RAW:
        item = None
        if kind == "video":
            vids = yt.videos([value])
            if vids:
                item = yt.channel_by_id(vids[0]["snippet"]["channelId"])
        else:
            for cand in handle_variants(value):
                item = yt.channel_by_handle(cand)
                if item:
                    break
        if item:
            st = item["statistics"]
            seeds[item["id"]] = {
                "channel_id": item["id"],
                "title": item["snippet"]["title"],
                "handle": item["snippet"].get("customUrl", ""),
                "subs": int(st.get("subscriberCount", 0)),
                "videos": int(st.get("videoCount", 0)),
                "views": int(st.get("viewCount", 0)),
                "country": item["snippet"].get("country", ""),
                "uploads_playlist": yt.uploads_playlist(item),
                "seed_label": label,
            }
            print("  OK   %-22s -> %-24s %s (%s subs, %s vids)" % (
                label, item["id"], item["snippet"]["title"],
                st.get("subscriberCount", "?"), st.get("videoCount", "?")))
        else:
            unresolved.append((label, value))
            print("  MISS %-22s (tried %d handle variants)" % (
                label, len(handle_variants(value))))

    json.dump({"seeds": seeds, "unresolved": unresolved},
              open(OUT, "w"), indent=1)
    print("\nResolved %d/%d seeds. Quota used today: %d units."
          % (len(seeds), len(RAW), yt.quota_used()))
    if unresolved:
        print("Unresolved (need search fallback):",
              ", ".join(l for l, _ in unresolved))
    return seeds


if __name__ == "__main__":
    resolve()
