"""Cross the creator pool with the HubSpot CRM export from Q for Media.

Answers, per pool creator: what is our standing with them — licence granted,
declined, in conversation, in the database but never contacted, or off the
radar entirely.

Join strategy, strongest first:
1. channel_id: HubSpot's YouTube field is /channel/UC... in 97% of the filled
   rows, and creator_channels.json already resolved the pool's channel IDs.
   Exact, no ambiguity.
2. handle: for rows whose YouTube field is /@handle.
3. normalised name equality (Name vs pool handle, [a-z0-9] only) — marked
   "aprox" so the dashboard can show it as such.

A creator can have several CRM records (batches, re-scouting). The creator's
status is the most advanced one: a granted licence anywhere wins, then an
explicit decline, then live conversation, and so on.

The raw CSV stays out of git (contact data); only this file's derived
data/qfm_status.json (handle + status, nothing personal) is versioned.
"""
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CSV = os.path.join(DATA, "hubspot_all.csv")
OUT = os.path.join(DATA, "qfm_status.json")

# Most advanced first. "Fair Use" is a usage decision, not a relationship, so
# it ranks below any actual contact.
PRECEDENCE = ["Granted", "Declined", "Connected", "Connected but Unresponsive",
              "Contacted", "Unresponsive", "Uncontactable", "To Contact",
              "Fair Use", "Not Existing Anymore", ""]

BUCKET = {
    "Granted": "licencia",
    "Declined": "rechazado",
    "Connected": "en curso",
    "Connected but Unresponsive": "en curso",
    "Contacted": "en curso",
    "Unresponsive": "sin respuesta",
    "Uncontactable": "sin respuesta",
    "To Contact": "por contactar",
    "Fair Use": "fair use",
    "Not Existing Anymore": "sin respuesta",
    "": "en bd",
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def build():
    rows = list(csv.DictReader(open(CSV)))
    by_cid, by_handle, by_name = {}, {}, {}
    for r in rows:
        u = r["YouTube"].strip()
        m = re.search(r"/channel/(UC[\w-]{22})", u)
        if m:
            by_cid.setdefault(m.group(1), []).append(r)
        m = re.search(r"/@([\w.\-]+)", u)
        if m:
            by_handle.setdefault(norm(m.group(1)), []).append(r)
        if r["Name"]:
            by_name.setdefault(norm(r["Name"]), []).append(r)

    cch = json.load(open(os.path.join(DATA, "creator_channels.json")))
    keys = {c["key"] for c in
            json.load(open(os.path.join(DATA, "creator_odds.json")))["creators"]}
    keys |= {c["key"] for c in
             json.load(open(os.path.join(DATA,
                                         "creator_priority.json")))["creators"]}

    out = {}
    for k in sorted(keys):
        c = cch.get(k) or {}
        recs, how = [], None
        for r in by_cid.get(c.get("channel_id"), []):
            recs.append(r); how = "cid"
        if not recs:
            for r in (by_handle.get(norm(c.get("handle"))) or
                      by_handle.get(k) or []):
                recs.append(r); how = "handle"
        if not recs:
            for r in by_name.get(k, []):
                recs.append(r); how = "aprox"
        if not recs:
            continue
        recs.sort(key=lambda r: PRECEDENCE.index(r["Status"])
                  if r["Status"] in PRECEDENCE else len(PRECEDENCE))
        best = recs[0]
        out[k] = {
            "status": best["Status"] or "En BD sin estado",
            "bucket": BUCKET.get(best["Status"], "en bd"),
            "score": best["Score"],
            "granted": best["Date Granted"][:10],
            "decline_reason": best["Decline Reason"],
            "hs_name": best["Name"],
            "records": len(recs),
            "match": how,
        }

    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    out = build()
    import collections
    print("Creadores del pool cruzados con HubSpot: %d" % len(out))
    for b, n in collections.Counter(v["bucket"] for v in out.values()).most_common():
        print("  %-14s %d" % (b, n))
    print("  (por nombre, aprox: %d)"
          % sum(1 for v in out.values() if v["match"] == "aprox"))
