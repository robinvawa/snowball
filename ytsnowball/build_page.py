"""Render the distributor map + video shortlist as a self-contained dashboard."""
import datetime as dt
import json
import statistics
import os
import re

import compare
import creators as creator_odds
import metrics
import qm_merge
import report

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

CSS = r"""
:root{
  --ground:#EEF1F3; --panel:#F7F9FA; --card:#FFFFFF; --ink:#10161B;
  --ink-2:#41525F; --ink-3:#71838F; --line:#D3DBE0;
  --accent:#14608F; --accent-soft:#DCE9F1;
  --signal:#B26B0C; --signal-soft:#F6E9D4;
  --alert:#9C2F26; --alert-soft:#F6DEDA;
  --good:#1E6B4F; --good-soft:#D9EDE4;
}
@media (prefers-color-scheme: dark){
  :root{
    --ground:#0C1116; --panel:#121A21; --card:#161F27; --ink:#E7EDF1;
    --ink-2:#A3B4C0; --ink-3:#71858F; --line:#25323C;
    --accent:#5AAEE0; --accent-soft:#153042;
    --signal:#E0A855; --signal-soft:#33260F;
    --alert:#E8827A; --alert-soft:#3A1E1B;
    --good:#63C79E; --good-soft:#123024;
  }
}
:root[data-theme="dark"]{
  --ground:#0C1116; --panel:#121A21; --card:#161F27; --ink:#E7EDF1;
  --ink-2:#A3B4C0; --ink-3:#71858F; --line:#25323C;
  --accent:#5AAEE0; --accent-soft:#153042;
  --signal:#E0A855; --signal-soft:#33260F;
  --alert:#E8827A; --alert-soft:#3A1E1B;
  --good:#63C79E; --good-soft:#123024;
}
:root[data-theme="light"]{
  --ground:#EEF1F3; --panel:#F7F9FA; --card:#FFFFFF; --ink:#10161B;
  --ink-2:#41525F; --ink-3:#71838F; --line:#D3DBE0;
  --accent:#14608F; --accent-soft:#DCE9F1;
  --signal:#B26B0C; --signal-soft:#F6E9D4;
  --alert:#9C2F26; --alert-soft:#F6DEDA;
  --good:#1E6B4F; --good-soft:#D9EDE4;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif;
  font-size:15px; line-height:1.5;
}
.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
.wrap{max-width:1240px; margin:0 auto; padding:0 24px 72px}

header.top{
  border-bottom:1px solid var(--line); background:var(--panel);
  padding:38px 0 0; margin-bottom:30px;
}
.eyebrow{
  font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:11px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--accent);
  margin:0 0 12px;
}
h1{
  font-size:clamp(27px,4.2vw,42px); line-height:1.08; margin:0 0 12px;
  letter-spacing:-.022em; font-weight:700; text-wrap:balance; max-width:20ch;
}
.sub{color:var(--ink-2); max-width:64ch; margin:0; font-size:15.5px}
.stats{
  display:grid; gap:1px; background:var(--line); border:1px solid var(--line);
  grid-template-columns:repeat(6,1fr); margin:28px 0 0;
}
@media (max-width:940px){.stats{grid-template-columns:repeat(3,1fr)}}
@media (max-width:520px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--card); padding:15px 17px; min-width:0}
.stat .n{
  font-family:ui-monospace,"SF Mono",Menlo,monospace;
  font-size:clamp(20px,2.2vw,26px); font-weight:600; letter-spacing:-.025em;
  font-variant-numeric:tabular-nums; display:block; line-height:1.15;
}
.stat .l{
  font-size:11px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--ink-3); margin-top:5px; display:block;
}
.stat.hot .n{color:var(--signal)}
.stat.warn .n{color:var(--alert)}

nav.tabs{display:flex; gap:2px; margin-top:26px; overflow-x:auto}
nav.tabs button{
  border:1px solid var(--line); border-bottom:0; background:var(--panel);
  color:var(--ink-2); font:inherit; font-size:14px; font-weight:600;
  padding:11px 18px; cursor:pointer; white-space:nowrap;
}
nav.tabs button[aria-selected=true]{
  background:var(--ground); color:var(--accent);
  box-shadow:inset 0 2px 0 var(--accent);
}
section[hidden]{display:none}
section{margin-top:8px}
h2{
  font-size:19px; letter-spacing:-.01em; margin:0 0 6px; font-weight:650;
  display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;
}
h2 .count{
  font-family:ui-monospace,Menlo,monospace; font-size:12px; color:var(--ink-3);
  font-weight:400; letter-spacing:.04em;
}
.lede{color:var(--ink-2); margin:0 0 16px; max-width:76ch; font-size:14.5px}
.lede b{color:var(--ink)}
h3.sub-h{font-size:14px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--ink-3); font-weight:650; margin:30px 0 10px;
  padding-bottom:6px; border-bottom:1px solid var(--line)}

.alert{
  border:1px solid var(--line); border-left:3px solid var(--alert);
  background:var(--card); padding:18px 20px; margin-top:20px;
}
.alert h3{margin:0 0 4px; font-size:15px; color:var(--alert); font-weight:650}
.alert p{margin:0 0 14px; color:var(--ink-2); font-size:14px; max-width:70ch}
.alert ul{margin:0; padding:0; list-style:none; display:grid; gap:7px}
.alert li{
  display:flex; gap:12px; align-items:baseline; flex-wrap:wrap;
  padding-bottom:7px; border-bottom:1px solid var(--line); font-size:14px;
}
.alert li:last-child{border-bottom:0; padding-bottom:0}
.alert li a{font-weight:600}

.controls{display:flex; gap:9px; flex-wrap:wrap; margin-bottom:13px; align-items:center}
input[type=search]{
  flex:1 1 210px; min-width:0; padding:9px 12px; border:1px solid var(--line);
  background:var(--card); color:var(--ink); font:inherit; font-size:14px;
}
input[type=search]:focus-visible,button:focus-visible,th:focus-visible{
  outline:2px solid var(--accent); outline-offset:1px;
}
.seg{display:flex; border:1px solid var(--line); background:var(--card)}
.seg button{
  border:0; background:transparent; color:var(--ink-2); font:inherit;
  font-size:13px; padding:9px 13px; cursor:pointer;
  border-right:1px solid var(--line); white-space:nowrap;
}
.seg button:last-child{border-right:0}
.seg button[aria-pressed=true]{background:var(--accent); color:#fff}
.seglabel{
  font-size:11px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--ink-3); font-weight:600;
}

.tbl{overflow-x:auto; border:1px solid var(--line); background:var(--card)}
table{border-collapse:collapse; width:100%; min-width:880px; font-size:13.5px}
th,td{padding:9px 11px; text-align:left; border-bottom:1px solid var(--line)}
thead th{
  position:sticky; top:0; background:var(--panel); z-index:2; cursor:pointer;
  font-size:10.5px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--ink-3); font-weight:600; white-space:nowrap; user-select:none;
}
thead th:hover{color:var(--accent)}
thead th[data-dir]:after{content:" \25BE"; color:var(--accent)}
thead th[data-dir=asc]:after{content:" \25B4"}
tbody tr:hover{background:var(--accent-soft)}
tbody tr:last-child td{border-bottom:0}
td.num{
  text-align:right; font-family:ui-monospace,Menlo,monospace;
  font-variant-numeric:tabular-nums; white-space:nowrap;
}
td.name{font-weight:600; min-width:230px; max-width:400px}
td .h{
  display:block; font-weight:400; font-size:11.5px; color:var(--ink-3);
  font-family:ui-monospace,Menlo,monospace; margin-top:2px;
}
a{color:var(--accent); text-decoration:none}
a:hover{text-decoration:underline}
.chip{
  display:inline-block; font-size:10px; letter-spacing:.05em; padding:2px 6px;
  text-transform:uppercase; font-weight:650; white-space:nowrap;
}
.chip.seed{background:var(--accent-soft); color:var(--accent)}
.chip.brand{background:var(--alert-soft); color:var(--alert)}
.chip.alta{background:var(--good-soft); color:var(--good)}
.chip.media{background:var(--signal-soft); color:var(--signal)}
.chip.baja{background:var(--alert-soft); color:var(--alert)}
.chip.unsure{background:var(--signal-soft); color:var(--signal)}
.bar{
  display:inline-block; width:44px; height:6px; background:var(--line);
  vertical-align:middle; margin-right:7px; position:relative;
}
.bar i{position:absolute; inset:0 auto 0 0; background:var(--accent)}
.bar.hi i{background:var(--good)}
.score{
  display:flex; align-items:center; gap:8px; font-family:ui-monospace,Menlo,monospace;
  font-variant-numeric:tabular-nums; font-weight:650;
}
.score .track{
  flex:0 0 34px; height:6px; background:var(--line); position:relative;
}
.score .track i{position:absolute; inset:0 auto 0 0; background:var(--signal)}

.vs{display:grid; gap:1px; background:var(--line); border:1px solid var(--line); margin-bottom:22px}
.vs .row{display:grid; grid-template-columns:1fr 150px 1fr; background:var(--card); align-items:center}
@media (max-width:640px){.vs .row{grid-template-columns:1fr 96px 1fr}}
.vs .lbl{
  text-align:center; font-size:10.5px; text-transform:uppercase;
  letter-spacing:.08em; color:var(--ink-3); font-weight:600; padding:10px 6px;
}
.vs .side{padding:10px 14px; font-family:ui-monospace,Menlo,monospace;
  font-variant-numeric:tabular-nums; font-size:14.5px; font-weight:600;
  display:flex; align-items:center; gap:9px}
.vs .side.them{color:var(--ink-2)}
.vs .side.us{color:var(--accent); justify-content:flex-end; text-align:right}
.vs .meter{height:8px; background:var(--line); flex:1; position:relative; min-width:26px}
.vs .meter i{position:absolute; top:0; bottom:0; background:var(--ink-3)}
.vs .side.us .meter i{background:var(--accent); right:0}
.vs .head{background:var(--panel); font-weight:650; font-size:11px;
  text-transform:uppercase; letter-spacing:.08em; color:var(--ink-3);
  padding:8px 14px}
.vs .head.us{text-align:right; color:var(--accent)}
.split{display:grid; grid-template-columns:repeat(3,1fr); gap:1px;
  background:var(--line); border:1px solid var(--line); margin-bottom:22px}
@media (max-width:640px){.split{grid-template-columns:1fr}}
.split div{background:var(--card); padding:14px 16px}
.split .n{font-family:ui-monospace,Menlo,monospace; font-size:24px;
  font-weight:600; display:block; font-variant-numeric:tabular-nums}
.split .l{font-size:11.5px; color:var(--ink-3); display:block; margin-top:4px}
.split .only-them .n{color:var(--signal)}
.split .only-us .n{color:var(--accent)}
details.method{margin-top:40px; border-top:1px solid var(--line); padding-top:18px}
details.method summary{cursor:pointer; font-weight:650; font-size:14px; color:var(--ink-2)}
details.method .body{
  padding-top:14px; color:var(--ink-2); font-size:14px; max-width:78ch;
  display:grid; gap:12px;
}
details.method ol,details.method ul{margin:0; padding-left:20px; display:grid; gap:7px}
code{
  font-family:ui-monospace,Menlo,monospace; font-size:12.5px;
  background:var(--panel); padding:1px 5px; border:1px solid var(--line);
}
.formula{
  background:var(--panel); border:1px solid var(--line); padding:12px 14px;
  font-family:ui-monospace,Menlo,monospace; font-size:12.5px; overflow-x:auto;
  color:var(--ink-2);
}
.foot{
  margin-top:34px; padding-top:16px; border-top:1px solid var(--line);
  color:var(--ink-3); font-size:12.5px;
}
@media (max-width:640px){
  .wrap{padding:0 16px 56px}
  header.top{padding:26px 0 0}
}
"""

JS = r"""
function fmt(n){return n==null?'—':Math.round(n).toLocaleString('es-ES')}
function kfmt(n){
  if(n>=1e6) return (n/1e6).toFixed(n>=1e7?0:1).replace('.',',')+' M';
  if(n>=1e3) return (n/1e3).toFixed(n>=1e5?0:1).replace('.',',')+' k';
  return String(n);
}
function wire(tableId, tbodyId, data, cols, filterFn, initKey){
  const table=document.getElementById(tableId);
  const sec=table.closest('section');
  const state={key:initKey||null, dir:'desc', q:'', seg:{}};
  sec.querySelectorAll('.seg').forEach(g=>{
    state.seg[g.dataset.group]=g.querySelector('[aria-pressed=true]').dataset.seg;
  });
  function view(){
    let rows=data.filter(r=>filterFn(r,state));
    if(state.key){
      const k=state.key, s=state.dir==='asc'?1:-1;
      rows=rows.slice().sort((a,b)=>{
        const x=a[k], y=b[k];
        if(typeof x==='string') return s*String(x).localeCompare(String(y));
        return s*((x||0)-(y||0));
      });
    }
    const MAX=600, shown=rows.slice(0,MAX);
    document.getElementById(tbodyId).innerHTML =
      shown.map(r=>'<tr>'+cols.map(c=>c(r)).join('')+'</tr>').join('');
    const c=sec.querySelector('.rowcount');
    if(c) c.textContent = rows.length>MAX
      ? ('mostrando '+MAX+' de '+rows.length)
      : (rows.length+' de '+data.length);
  }
  table.querySelectorAll('th[data-k]').forEach(th=>{
    th.tabIndex=0;
    const go=()=>{
      const k=th.dataset.k;
      state.dir=(state.key===k && state.dir==='desc')?'asc':'desc';
      state.key=k;
      table.querySelectorAll('th').forEach(o=>o.removeAttribute('data-dir'));
      th.dataset.dir=state.dir;
      view();
    };
    th.addEventListener('click',go);
    th.addEventListener('keydown',e=>{
      if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}
    });
  });
  const inp=sec.querySelector('input[type=search]');
  if(inp) inp.addEventListener('input',e=>{state.q=e.target.value.toLowerCase();view();});
  sec.querySelectorAll('.seg').forEach(g=>{
    g.querySelectorAll('button').forEach(b=>{
      b.addEventListener('click',()=>{
        g.querySelectorAll('button').forEach(o=>o.setAttribute('aria-pressed','false'));
        b.setAttribute('aria-pressed','true');
        state.seg[g.dataset.group]=b.dataset.seg;
        view();
      });
    });
  });
  view();
}
document.querySelectorAll('nav.tabs button').forEach(b=>{
  b.addEventListener('click',()=>{
    document.querySelectorAll('nav.tabs button').forEach(o=>o.setAttribute('aria-selected','false'));
    b.setAttribute('aria-selected','true');
    document.querySelectorAll('main > section').forEach(s=>{
      s.hidden = (s.id !== b.dataset.tab);
    });
  });
});
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def main():
    today = dt.date.today()
    dist, pool = report.main()
    vids = metrics.main(today)

    ours_n = next((p["distributors"] for p in pool
                   if re.sub(r"[^a-z0-9]", "", p["creator"].lower())
                   == "quantummakers"), 0)
    looks = [r for r in dist if r["brand_lookalike"]]
    new_n = sum(1 for r in dist if not r["is_seed"])
    subs_total = sum(r["subs"] for r in dist)
    pool_hot = [p for p in pool if p["distributors"] >= 3]
    in_scope = [v for v in vids if v["scope"] == "in"]

    v_json = json.dumps([{
        "t": v["title"], "id": v["video_id"], "ch": v["channel_title"],
        "vw": v["views"], "pv": v["perpetuity_views"], "po": v["perp_outlier"],
        "ag": v["age_days"], "cf": v["confidence"], "sc": v["scope"],
        "sr": v["scope_reason"], "xw": v["xd_winners"], "xd": v["xd_distributors"],
        "sk": v["interest"], "cr": (v["source_handles_title"] or [""])[0],
        "ex": (round(v["perpetuity_views"] * (1 - 1 / v["perp_outlier"]))
               if v["perp_outlier"] > 1 else 0),
    } for v in vids if v["scope"] != "out"], ensure_ascii=False)

    # Per-distributor perpetuity averages. "Views" always means projected
    # lifetime views when videos are being compared — raw counts penalise
    # whoever published most recently.
    full = json.load(open(os.path.join(HERE, "data", "full_catalog.json")))
    scored = json.load(open(os.path.join(HERE, "data", "scored_videos.json")))
    per_ch = {}
    for v in scored:
        if v["scope"] == "out":
            continue
        p = per_ch.setdefault(v["channel_id"], {"all": [], "r90": []})
        p["all"].append(v["perpetuity_views"])
        if v["age_days"] <= 90:
            p["r90"].append(v["perpetuity_views"])

    # A channel earns its place only by publishing at least one long-form video
    # inside our content space. Nothing else about it matters: no long videos at
    # all (shorts channels), or long videos that are all off-topic, and it is
    # not a distributor we can use.
    def _usable(r):
        f = full.get(r["channel_id"]) or {}
        if f.get("n"):
            return bool(f.get("n_in_scope"))
        # No full catalogue: fall back to the harvested sample.
        return any(v["scope"] == "in" for v in scored
                   if v["channel_id"] == r["channel_id"])

    dropped = [r for r in dist if not _usable(r)]
    for r in dropped:
        f = full.get(r["channel_id"]) or {}
        print("   excluido — %s: %s" % (
            "ni un vídeo largo" if not f.get("n")
            else "%d largos, ninguno de nuestro espacio" % f["n"], r["title"]))
    dist = [r for r in dist if r not in dropped]

    d_json = json.dumps([{
        "t": r["title"], "h": r["handle"], "u": r["url"], "s": r["subs"],
        # Everything below comes from the channel's FULL catalogue with shorts
        # and live placeholders removed, not from YouTube's own counters and
        # not from the 50-video sample.
        # Fall back to the 50-video sample for the handful of channels whose
        # full catalogue could not be fetched, so no row shows a false zero.
        "v": ((full.get(r["channel_id"]) or {}).get("n_in_scope")
              or len(per_ch.get(r["channel_id"], {}).get("all", []))),
        "vlong": (full.get(r["channel_id"]) or {}).get("n", 0),
        "part": not (full.get(r["channel_id"]) or {}).get("n"),
        "vy": r["videos"],
        "sh": max(0, (full.get(r["channel_id"]) or {}).get("shorts_excluded", 0)),
        "cap": (full.get(r["channel_id"]) or {}).get("n_reported", 0) > 400,
        # Median duration. Channels sitting on the 3-minute line get their
        # catalogue split arbitrarily by the cut-off, so their figures come
        # from a biased half and must be read with that in mind.
        "dur": (full.get(r["channel_id"]) or {}).get("median_secs", 0),
        # Median, not mean: views per video are heavy-tailed, and in 59% of
        # these channels the mean runs 2x+ the median because one viral upload
        # carries it. The median describes the typical video.
        # Typical performance over the channel's in-scope long videos only.
        "a": ((full.get(r["channel_id"]) or {}).get("perp_median_in")
              or (full.get(r["channel_id"]) or {}).get("perp_median")
              or (round(sum(per_ch[r["channel_id"]]["all"])
                        / len(per_ch[r["channel_id"]]["all"]))
                  if per_ch.get(r["channel_id"], {}).get("all") else 0)),
        "r90": ((full.get(r["channel_id"]) or {}).get("perp_90d_median")
                or (round(statistics.median(per_ch[r["channel_id"]]["r90"]))
                    if per_ch.get(r["channel_id"], {}).get("r90") else None)),
        "n90": ((full.get(r["channel_id"]) or {}).get("n_90d")
                or len(per_ch.get(r["channel_id"], {}).get("r90", []))),
        "c": (len((full.get(r["channel_id"]) or {}).get("creators", []))
              or r["creators_covered"]),
        "r": (full.get(r["channel_id"]) or {}).get("attribution",
                                                   r.get("attribution_rate", 0)),
        "rr": r.get("attribution_rate", 0),
        "seed": r["is_seed"],
        "brand": r["brand_lookalike"],
    } for r in dist], ensure_ascii=False)

    # Destacado reciente: en-scope, publicado en las ultimas 8 semanas.
    # "Nuevo en el pool" = la primera cobertura del creador en TODO el dataset
    # cae dentro de la ventana.
    RECENT_D = 56
    first_seen = {}
    for v in vids:
        for h in v.get("source_handles_title") or []:
            k = metrics.norm(h)
            if k and (k not in first_seen or v["published"] < first_seen[k]):
                first_seen[k] = v["published"]
    recent = [v for v in vids
              if v["scope"] != "out" and v["age_days"] <= RECENT_D
              and v["perp_outlier"] >= 1.5]
    def _is_new(v):
        for h in v.get("source_handles_title") or []:
            k = metrics.norm(h)
            if k and first_seen.get(k) == v["published"]:
                return True
        return False
    n_json = json.dumps([{
        "id": v["video_id"], "t": v["title"], "ch": v["channel_title"],
        "cr": (v.get("source_handles_title") or [""])[0],
        "vw": v["views"], "pv": v["perpetuity_views"],
        "po": v["perp_outlier"], "ag": v["age_days"],
        "ex": round(v["perpetuity_views"] * (1 - 1 / v["perp_outlier"])),
        "xw": v["xd_winners"], "nw": _is_new(v),
    } for v in sorted(recent,
                      key=lambda v: -v["perpetuity_views"]
                      * (1 - 1 / v["perp_outlier"]))],
        ensure_ascii=False)

    # Movimiento entre refrescos: views ganadas desde el snapshot anterior.
    # Misma logica que el ranking, pero sobre crecimiento MEDIDO, no proyectado:
    # de las views nuevas de cada video se resta la mediana de views nuevas de
    # su canal en la misma ventana (lo que gana ahi un video "normal").
    delta_rows, delta_date = [], None
    prev_p = os.path.join(HERE, "data", "views_prev.json")
    if os.path.exists(prev_p):
        snap = json.load(open(prev_p))
        prevv, delta_date = snap["views"], snap["date"]
        by_ch_dv = {}
        cand = []
        for v in vids:
            vid = v["video_id"]
            if vid in prevv:
                dv, nw2 = max(0, v["views"] - prevv[vid]), False
            elif v["published"][:10] >= delta_date:
                dv, nw2 = v["views"], True   # subido tras el snapshot
            else:
                continue                     # recuperado viejo: delta no medible
            by_ch_dv.setdefault(v["channel_id"], []).append(dv)
            cand.append((dv, nw2, v))
        med_dv = {c: statistics.median(x) for c, x in by_ch_dv.items()}
        for dv, nw2, v in cand:
            ad = max(0, dv - med_dv.get(v["channel_id"], 0))
            if v["scope"] == "out" or (ad < 1000 and not nw2):
                continue
            delta_rows.append({
                "id": v["video_id"], "t": v["title"], "ch": v["channel_title"],
                "cr": (v.get("source_handles_title") or [""])[0],
                "dv": dv, "ad": round(ad), "vw": v["views"],
                "po": v["perp_outlier"], "ag": v["age_days"], "nw": nw2,
            })
        delta_rows.sort(key=lambda r: -r["ad"])
        delta_rows = delta_rows[:600]
    dl_json = json.dumps(delta_rows, ensure_ascii=False)

    odds = creator_odds.build()
    p_json = json.dumps([{
        "t": c["creator"], "u": c["url"], "od": c["odds_top"],
        "sc": c["attr_views"], "bx": c["best_excess"],
        "fz": c["best_strength"], "cf": c["confirmations"],
        "d": c["distributors"], "ol": c["best_outlier"], "rc": c["best_reach"],
        "ch": c["best_channel"], "cs": c["best_channel_subs"],
        "ev": c["evidence"], "bt": c["best_title"], "bv": c["best_video"],
    } for c in odds], ensure_ascii=False)
    n_lift = sum(1 for c in odds if c["odds_top"] >= 0.9)

    import model as creator_model
    creator_model.build()
    cch = json.load(open(os.path.join(HERE, "data", "creator_channels.json")))
    cmp = compare.build()
    # La pestaña de prioridad se retiro (ordenaba por tasa base de grupo, no por
    # creador), pero qm_merge sigue corriendo: alimenta las dos cifras de cabecera.
    prio, _ = qm_merge.build()
    n_mina = sum(1 for r in prio if r["status"] == "probado_ok")
    n_new = sum(1 for r in prio if r["status"] == "sin_explorar")

    looks_html = "".join(
        '<li><a href="{u}" target="_blank" rel="noopener">{t}</a>'
        '<span class="mono" style="color:var(--ink-3);font-size:12.5px">{h}</span>'
        '<span class="mono" style="margin-left:auto;font-variant-numeric:tabular-nums">'
        '{s} subs &middot; {v} v&iacute;deos</span></li>'.format(
            u=esc(r["url"]), t=esc(r["title"]), h=esc(r["handle"]),
            s=f"{r['subs']:,}".replace(",", "."), v=r["videos"])
        for r in sorted(looks, key=lambda r: -r["subs"]))

    tmpl = open(os.path.join(HERE, "page.tmpl.html")).read()
    html = (tmpl
            .replace("__CSS__", CSS)
            .replace("__JS__", JS)
            .replace("__VJSON__", v_json)
            .replace("__DJSON__", d_json)
            .replace("__PJSON__", p_json)
            .replace("__NJSON__", n_json)
            .replace("__DLJSON__", dl_json)
            .replace("__DLDATE__", delta_date or "—")
            .replace("__LOOKS__", looks_html)
            .replace("__N_DIST__", str(len(dist)))
            .replace("__N_NEW__", str(new_n))
            .replace("__SUBS__", ("%.1f M" % (subs_total / 1e6)).replace(".", ","))
            .replace("__N_POOL__", str(len(pool)))
            .replace("__N_HOT__", str(len(pool_hot)))
            .replace("__N_LOOKS__", str(len(looks)))
            .replace("__N_OURS__", str(ours_n))
            .replace("__N_VIDS__", f"{len(in_scope):,}".replace(",", "."))
            .replace("__N_OUT__", str(sum(1 for v in vids if v["scope"] == "out")))
            .replace("__N_ALL__", f"{len(vids):,}".replace(",", "."))
            .replace("__N_IN__", f"{len(in_scope):,}".replace(",", "."))
            .replace("__N_LIFT__", str(n_lift))
            .replace("__STRONGPCT__", "%.0f" % (100 * creator_odds.STRONG))
            .replace("__N_MINA__", str(n_mina))
            .replace("__N_UNEXP__", str(n_new))
            .replace("__CJSON__", json.dumps(cmp["agg"], ensure_ascii=False))
            .replace("__GJSON__", json.dumps([{
                "t": g["creator"], "u": g["url"], "d": g["distributors"],
                "r": g["best_reach"], "o": g["best_outlier"],
                "s": g["creator_subs"], "bt": g["best_title"],
                "bv": g["best_video"], "ls": g["last_seen"],
            } for g in cmp["gap"] if g["distributors"] >= 2], ensure_ascii=False))
            .replace("__RJSON__", json.dumps([{
                "t": c["title"], "u": c["url"], "h": c["handle"],
                "s": c["subs"], "n": c["creators"], "x": c["exclusive"],
                "ov": c["overlap_pct"], "ld": c["lead"], "fw": c["follow"],
                "lag": c["median_lag"], "bs": c["brand_sim"],
                "bt": c["brand_tokens"],
            } for c in cmp["channels"]], ensure_ascii=False))
            .replace("__TJSON__", json.dumps(cmp["topics"], ensure_ascii=False))
            .replace("__N_GAP__", str(sum(1 for g in cmp["gap"]
                                          if g["distributors"] >= 3)))
            .replace("__N_BRAND2__", str(sum(1 for c in cmp["channels"]
                                             if c["brand_sim"] >= 0.5)))
            .replace("__DATE__", today.strftime("%d/%m/%Y")))

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "distributor_map.html")
    open(path, "w").write(html)
    print("\nWrote %s (%.0f KB)" % (path, os.path.getsize(path) / 1024))
    return path


if __name__ == "__main__":
    main()
