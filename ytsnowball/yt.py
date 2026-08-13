"""Minimal YouTube Data API v3 client: stdlib only, disk-cached, quota-tracked."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://www.googleapis.com/youtube/v3/"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache")
QUOTA_FILE = os.path.join(HERE, "data", "quota.json")

# Documented quota cost per endpoint.
COST = {"search": 100, "channels": 1, "playlistItems": 1, "videos": 1}


def _key():
    for line in open(os.path.join(HERE, ".env")):
        if line.startswith("YOUTUBE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("YOUTUBE_API_KEY missing from .env")


def _quota():
    day = time.strftime("%Y-%m-%d")
    try:
        q = json.load(open(QUOTA_FILE))
    except Exception:
        q = {}
    if q.get("day") != day:
        q = {"day": day, "used": 0}
    return q


def quota_used():
    return _quota()["used"]


def _charge(endpoint):
    q = _quota()
    q["used"] += COST.get(endpoint, 1)
    os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
    json.dump(q, open(QUOTA_FILE, "w"))


class QuotaExceeded(Exception):
    pass


def call(endpoint, cache=True, **params):
    """One API call. Cached by (endpoint, params) so re-runs are free."""
    params = {k: v for k, v in params.items() if v is not None}
    sig = hashlib.sha1(
        (endpoint + json.dumps(params, sort_keys=True)).encode()
    ).hexdigest()
    path = os.path.join(CACHE, endpoint, sig + ".json")
    if cache and os.path.exists(path):
        return json.load(open(path))

    url = BASE + endpoint + "?" + urllib.parse.urlencode(dict(params, key=_key()))
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            # 403 = project quota; 429 = the separate per-day Search Queries cap.
            if e.code in (403, 429) and "quota" in body.lower():
                raise QuotaExceeded(body[:300])
            if e.code in (500, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError("HTTP %s on %s: %s" % (e.code, endpoint, body[:300]))
        except Exception:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    _charge(endpoint)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w"))
    return data


def channel_by_handle(handle):
    r = call("channels", part="snippet,statistics,contentDetails",
             forHandle=handle.lstrip("@"))
    items = r.get("items") or []
    return items[0] if items else None


def channel_by_id(cid):
    r = call("channels", part="snippet,statistics,contentDetails", id=cid)
    items = r.get("items") or []
    return items[0] if items else None


def channels_by_ids(ids):
    """Batch up to 50 channel IDs per call (1 unit each call)."""
    out = {}
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 50):
        r = call("channels", part="snippet,statistics,contentDetails",
                 id=",".join(ids[i:i + 50]))
        for it in r.get("items", []):
            out[it["id"]] = it
    return out


def uploads_playlist(channel_item):
    return channel_item["contentDetails"]["relatedPlaylists"]["uploads"]


def playlist_videos(playlist_id, limit=50):
    """Video IDs from an uploads playlist, newest first. 1 unit per 50."""
    ids, token = [], None
    while len(ids) < limit:
        r = call("playlistItems", part="contentDetails", playlistId=playlist_id,
                 maxResults=min(50, limit - len(ids)), pageToken=token)
        for it in r.get("items", []):
            ids.append(it["contentDetails"]["videoId"])
        token = r.get("nextPageToken")
        if not token:
            break
    return ids


def videos(video_ids):
    """Full video records, batched 50 per call (1 unit each)."""
    out = []
    ids = list(dict.fromkeys(video_ids))
    for i in range(0, len(ids), 50):
        r = call("videos", part="snippet,statistics,contentDetails",
                 id=",".join(ids[i:i + 50]))
        out.extend(r.get("items", []))
    return out


def search(query, max_results=25, **extra):
    """Keyword search. EXPENSIVE: 100 units per call."""
    r = call("search", part="snippet", q=query, type="video",
             maxResults=max_results, **extra)
    return r.get("items", [])
