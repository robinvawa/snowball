"""Extract source-creator attributions (@handles) and topic keys from videos."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# Handles as written in titles/descriptions. Unicode-aware: several source
# creators are Cyrillic (@КарельскийДилетант).
HANDLE_RE = re.compile(r"@([\wЀ-ӿÀ-ɏ][\wЀ-ӿÀ-ɏ.\-]{2,29})")

# Junk that shows up as @-tokens but is not a creator.
STOP = {"gmail", "outlook", "yahoo", "hotmail", "youtube", "shorts", "instagram",
        "proton", "protonmail", "icloud", "mail", "email", "contact", "info",
        "business", "yandex", "naver", "gmx", "aol", "mailfence", "zoho"}
# An email in a description ("someone@gmail.com") captures "gmail.com", so
# matching the bare stopword never fired. Strip the TLD before the check, and
# treat anything still carrying one as a domain rather than a channel handle.
TLD = re.compile(r"\.(com|net|org|ru|co|io|es|fr|de|br|uk|info|me|tv|xyz|"
                 r"online|site|shop|store|biz|edu|gov|agency|studio|media|"
                 r"pro|app|dev|link|page|live|team|group)$", re.I)
# Descriptions often paste a raw channel URL; the id is not a handle.
RAW_ID = re.compile(r"^UC[\w-]{20,24}$")

# Topic vocabulary of this niche: what the build IS.
TOPICS = [
    ("shipping_container", r"shipping container|container home|containers into"),
    ("school_bus", r"school bus|bus conversion|skoolie"),
    ("boat", r"\bboat\b|canoe|raft|yacht|catamaran"),
    ("underground_bunker", r"bunker|underground (shelter|house|hideout)|dugout"),
    ("log_cabin", r"log (cabin|house|home)|wooden (cabin|house|mansion)"),
    ("a_frame", r"a-frame|a frame cabin"),
    ("treehouse", r"tree ?house|in a tree|inside a (giant )?tree"),
    ("tiny_house", r"tiny (house|home)"),
    ("restoration", r"restor|renovat|abandoned|forgotten|100-year|century-old"),
    ("silo_barn", r"\bsilo\b|\bbarn\b|grain bin"),
    ("water_tank", r"water tank|tanks into"),
    ("earthship", r"tire house|earthship|rammed earth|cob house"),
    ("off_grid", r"off.?grid|self.?sufficient|homestead"),
    ("truck_van", r"\bvan\b|truck|camper|motorhome|military vehicle|rv\b"),
    ("castle", r"castle|chateau|fortress"),
    ("pool_sauna", r"\bpool\b|sauna|hot tub"),
    ("machine_build", r"machine|engine|drone|excavator|tractor|forge|cnc"),
    ("concrete_house", r"concrete|aerated block|brick house|stone house"),
]


def handles(text):
    out = []
    for m in HANDLE_RE.finditer(text or ""):
        h = m.group(1).rstrip(".-")
        if len(h) < 3:
            continue
        if TLD.sub("", h).lower() in STOP or TLD.search(h) or RAW_ID.match(h):
            continue
        out.append(h)
    return out


def topics(text):
    t = (text or "").lower()
    return [name for name, pat in TOPICS if re.search(pat, t)]


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def enrich(videos):
    for v in videos:
        title_h = handles(v["title"])
        desc_h = handles(v.get("description", ""))
        # A title credit is the primary source; description credits are weaker
        # (they include the distributor's own socials and unrelated mentions).
        # Drop the channel's own handle: crediting yourself is not sourcing.
        own = {_norm(v.get("channel_title"))}
        v["source_handles_title"] = title_h
        v["source_handles_desc"] = [h for h in desc_h
                                    if h not in title_h and _norm(h) not in own]
        v["source_handle"] = title_h[0] if title_h else (desc_h[0] if desc_h else None)
        v["topics"] = topics(v["title"] + " " + v.get("description", "")[:400])
    return videos


if __name__ == "__main__":
    import collections
    vids = enrich(json.load(open(os.path.join(HERE, "data", "seed_videos.json"))))
    json.dump(vids, open(os.path.join(HERE, "data", "seed_videos.json"), "w"), indent=1)

    credited = [v for v in vids if v["source_handles_title"]]
    print("Videos with a source creator credited in the TITLE: %d/%d (%.0f%%)"
          % (len(credited), len(vids), 100 * len(credited) / len(vids)))

    # Which source creators are covered by more than one distributor?
    src = collections.defaultdict(set)
    for v in vids:
        for h in v["source_handles_title"]:
            src[h.lower()].add(v["channel_title"])
    shared = {k: v for k, v in src.items() if len(v) > 1}
    print("Distinct source creators credited: %d" % len(src))
    print("Covered by 2+ seed distributors:   %d\n" % len(shared))
    for k, v in sorted(shared.items(), key=lambda x: -len(x[1])):
        print("  @%-24s %d channels: %s" % (k, len(v), ", ".join(sorted(v))))

    print("\nTop topics:")
    tc = collections.Counter(t for v in vids for t in v["topics"])
    for t, n in tc.most_common(12):
        print("  %-20s %d" % (t, n))
