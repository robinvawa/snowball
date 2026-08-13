"""Decide whether a distributor video is inside Quantum Makers' content space.

Bias: conservative. We only mark 'out' on a strong negative signal with no
positive evidence, so nothing genuinely relevant gets hidden. The one hard rule
is length: under three minutes is out regardless of any other evidence.
"""
import re

import shape

MIN_SECONDS = 180  # nothing shorter is usable as DV source material

# Single-project build/craft documentaries, across the languages these
# distributors actually publish in.
BUILD = re.compile(
    r"build|built|buil[dt]s|hous|home|cabin|cottage|lodge|boat|ship|yacht|"
    r"canoe|kayak|raft|container|bunker|shed|barn|silo|tiny |off.?grid|"
    r"renovat|restor|transform|convert|remodel|craft|wood|timber|log |"
    r"truck|van\b|bus\b|camper|motorhome|caravan|trailer|forge|workshop|"
    r"\bdiy\b|constru|garage|shelter|dome|tree ?house|yurt|pool|sauna|"
    r"tunnel|underground|dugout|farm|homestead|hut|villa|mansion|castle|"
    r"chateau|greenhouse|solar|weld|excavat|tractor|bushcraft|cave|"
    r"workshop|carpent|mason|brick|concrete|foundation|roof|"
    # Spanish / Portuguese
    r"casa|constru|cabaña|cabana|refugi|madera|madeira|barco|contenedor|"
    r"reforma|restaur|taller|subterr|caba|vivienda|"
    # French
    r"maison|cabane|bateau|rénov|renov|bois|abri|atelier|chalet|"
    # Vietnamese
    r"nhà|xây|gỗ|thuyền|rừng|hầm|"
    # Russian / Ukrainian
    r"дом|стро|бан|сруб|землянк|избу|избы|хижин|"
    # Turkish
    r"\bev\b|inşa|kulübe|ahşap|yapı|"
    # Indonesian / German / Polish
    r"rumah|bangun|kayu|haus|hütte|holz|\bdom\b|buduje",
    re.I)

# Formats that are clearly a different genre, not a single-project build.
NEGATIVE = [
    ("listicle", re.compile(
        r"^\s*(top\s*)?\d{1,3}\s+(incredible|amazing|insane|best|smart|"
        r"affordable|future|genius|coolest|craziest|most|new|unbelievable|"
        r"inventions|gadgets|machines|tools|things|technologies|devices|"
        r"vehicles|cars|bikes|products|ideas)|"
        r"\btop\s*\d{1,3}\b|"
        r"\b\d{1,3}\s+(inventions|gadgets|technologies|devices|products|"
        r"ideas|things you|machines that|tools that)", re.I)),
    ("gadget_roundup", re.compile(
        r"\binventions?\b(?!.*\bbuil)|\bgadgets?\b|you won'?t believe|"
        r"aren'?t telling you|change the world|change everything|"
        r"amazing products|coolest (tech|gadgets)", re.I)),
    ("celebrity", re.compile(
        r"then and now|cast of|actors? who|remembering |died|passed away|"
        r"tribute|biography|net worth|before they were", re.I)),
    ("factory", re.compile(
        r"how .{2,30} is made|factory (process|skills|tour)|mass production|"
        r"production line|manufacturing process", re.I)),
    ("reaction_meme", re.compile(
        r"\breact(ion|s|ing)\b|\bprank\b|\bfunny\b|caught on camera|"
        r"nobody expected|look twice|#shorts|#shortsfeed|#viral|"
        r"satisfying videos", re.I)),
    ("aita_text", re.compile(
        r"^(aita|wibta|for (not )?\w+ing\b)|\bmy (sil|mil|bf|gf)\b|"
        r"am i the (a|jerk)", re.I)),
    ("news_list", re.compile(
        r"\bnews\b|\bstock\b|\bcrypto\b|\bbitcoin\b|\btrailer\b(?! build)|"
        r"\bepisode \d|\bpodcast\b", re.I)),
]


def iso_seconds(dur):
    """PT#H#M#S -> seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def classify(v):
    """-> (verdict, reason). verdict in {'in','unsure','out'}."""
    title = v.get("title", "")
    secs = iso_seconds(v.get("duration"))
    v["seconds"] = secs

    attributed = bool(v.get("source_handles_title"))

    # Duration gate first, and it overrides everything: anything under three
    # minutes is not usable as DV source material, credited creator or not.
    if secs <= MIN_SECONDS:
        return "out", ("duración desconocida" if not secs
                       else "short de %dm%02ds" % (secs // 60, secs % 60))

    # A credited source creator is decisive: that is exactly our raw pool.
    if attributed:
        return "in", "acredita creador fuente"

    if v.get("source_handles_desc"):
        return "in", "acredita en la descripción"

    # No credit anywhere — but plenty of real D1/DV uploads simply never credit
    # the creator, and the title still shows what they are: a singular subject
    # doing one build. Compilations read differently and stay out.
    single, why = shape.looks_single_project(title)
    if single:
        return "in", "sin crédito, pero forma de proyecto único (%s)" % why
    return "out", why


def apply(videos):
    for v in videos:
        v["scope"], v["scope_reason"] = classify(v)
    return videos
