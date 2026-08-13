"""Reliable YouTube Shorts detection.

Duration alone is not enough. YouTube raised the Shorts ceiling to three
minutes, so a video of exactly 180s is a Short — and encoding overhead means
some come back as 181s. Measured on real uploads:

    <= 180s   always a Short
    181s      still a Short (TK Maker's uploads)
    >= 190s   not a Short

So anything at or under 180s is excluded on duration, anything comfortably above
the ceiling is accepted, and the narrow grey zone between is resolved by asking
YouTube directly: /shorts/<id> stays on that path for a Short and redirects to
/watch otherwise. Costs no API quota, and results are cached to disk.
"""
import json
import os
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "shorts_cache.json")

CERTAIN_SHORT = 180   # at or below: a Short, no check needed
CERTAIN_LONG = 300    # above: cannot be a Short

_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(CACHE))
        except Exception:
            _cache = {}
    return _cache


def save():
    if _cache is not None:
        json.dump(_cache, open(CACHE, "w"))


def check_url(video_id, timeout=15):
    """Ask YouTube. True = Short, False = regular, None = could not tell."""
    c = _load()
    if video_id in c:
        return c[video_id]
    req = urllib.request.Request(
        "https://www.youtube.com/shorts/" + video_id, method="HEAD",
        headers={"User-Agent": "Mozilla/5.0"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        res = "/shorts/" in r.url
    except urllib.error.HTTPError:
        res = False
    except Exception:
        return None  # transient: do not cache
    c[video_id] = res
    return res


def is_short(seconds, video_id=None):
    """Verdict for one video. Unknown duration counts as a Short: if we cannot
    prove it clears the bar, it does not enter the dataset."""
    if not seconds:
        return True
    if seconds <= CERTAIN_SHORT:
        return True
    if seconds > CERTAIN_LONG:
        return False
    if video_id is None:
        return True  # grey zone with no way to check: exclude
    res = check_url(video_id)
    return True if res is None else res
