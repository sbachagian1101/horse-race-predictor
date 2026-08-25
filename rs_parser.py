"""Robust Racing & Sports thoroughbred Enhanced Form paste parser."""
from __future__ import annotations

import re
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace("$", "").replace(",", "").replace("%", "").strip())
    except Exception:
        return default


def _name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def _clean(text: str) -> str:
    text = str(text or "").replace("\xa0", " ").replace("\u2003", " ").replace("\u2002", " ").replace("\u202f", " ")
    text = text.replace("\\-", "-").replace("\\:", ":").replace("\\&", "&")
    text = re.sub(r"\[([^\]]+)\]\([^\n]*?\)", r"\1", text)
    text = text.replace("***", "").replace("**", "").replace("__", "")
    text = re.sub(r"^[#>*]+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*]\s+(?=[A-Za-z\[])", "", text, flags=re.M)
    return "\n".join(line.strip() for line in text.splitlines())


def _link(cell: str) -> str:
    m = re.search(r"\[\**([^\]]+?)\**\]\(", cell)
    return (m.group(1) if m else re.sub(r"[\[\]*]", "", cell)).strip()


def parse_race_header(raw: str) -> dict[str, Any]:
    t = _clean(raw); h: dict[str, Any] = {}
    m = re.search(r"(?mi)^(.+?)\s+Form Guide\s*\(Race\s*(\d+)\)", t)
    if m: h["track"], h["race_no"] = m.group(1).strip(), int(m.group(2))
    m = re.search(r"(?mi)^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(.+?\d{4})$", t)
    if m: h["date"] = f"{m.group(1)}, {m.group(2)}"
    m = re.search(r"(?is)\(local\)\s*\n+\s*([^\n]+?)\s*\n+\s*WT:", t)
    if m: h["race_name"] = m.group(1).strip()
    m = re.search(r"(?i)Type:\s*([^\s\n]+)", t)
    if m: h["race_class"] = m.group(1).strip()
    m = re.search(r"AUD\s*\$([\d,]+)", t, re.I)
    if m: h["prize"] = f"AUD ${m.group(1)}"
    m = re.search(r"(?mi)^(\d{3,4})m\s+(TURF|AW|SAND|DIRT|POLY)\s+([A-Z]+(?:\s+\d+)?)\s*$", t)
    if m:
        h["distance_m"] = int(m.group(1)); h["surface"] = m.group(2).upper(); h["going"] = m.group(3).upper()
    return h


def _summary_markdown(raw: str) -> list[dict[str, Any]]:
    out = []
    for line in raw.splitlines():
        if not re.match(r"^\|\s*\d{1,2}\s*\|", line.strip()): continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 8: continue
        n = re.sub(r"\D", "", cells[0])
        if not n or not re.fullmatch(r"\d{2,3}(?:\.\d+)?", re.sub(r"[* ]", "", cells[2])): continue
        tab = int(n); jockey_raw = _link(cells[4]); cm = re.search(r"\(a(\d+(?:\.\d+)?)\)", jockey_raw, re.I)
        scratched = any(re.search(r"\bscr\b", c, re.I) for c in cells[8:]); odds = 999.0
        for c in reversed(cells[8:]):
            c2 = re.sub(r"[*$]", "", c).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", c2): odds = _f(c2, 999.0); break
        out.append({
            "tab": tab, "horse": _name(_link(cells[1])), "wt": _f(cells[2]), "bp": int(_f(cells[3], 0)),
            "jockey": _name(re.sub(r"\s*\(a\d+(?:\.\d+)?\)", "", jockey_raw, flags=re.I)),
            "claim": _f(cm.group(1)) if cm else 0.0, "jrat": _f(re.sub(r"^\**H\**\s*", "", cells[5], flags=re.I)),
            "trainer": _name(_link(cells[6])), "trat": _f(re.sub(r"^\**H\**\s*", "", cells[7], flags=re.I)),
            "tab_odds": 999.0 if scratched else odds, "scratched": scratched,
        })
    return out


def _summary_plain(raw: str) -> list[dict[str, Any]]:
    out = []
    for line in _clean(raw).splitlines():
        p = [x.strip() for x in line.split("\t")]
        if len(p) < 8 or not re.fullmatch(r"\d{1,2}", p[0]) or not re.fullmatch(r"\d{2,3}(?:\.\d+)?", p[2]): continue
        jr = p[4]; cm = re.search(r"\(a(\d+(?:\.\d+)?)\)", jr, re.I); scr = any(re.search(r"\bscr\b", x, re.I) for x in p[8:]); odds=999.0
        for x in reversed(p[8:]):
            x2=re.sub(r"[$*]", "", x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", x2): odds=_f(x2,999.0); break
        out.append({"tab":int(p[0]),"horse":_name(p[1]),"wt":_f(p[2]),"bp":int(_f(p[3],0)),"jockey":_name(re.sub(r"\s*\(a\d+(?:\.\d+)?\)","",jr,flags=re.I)),"claim":_f(cm.group(1)) if cm else 0.0,"jrat":_f(re.sub(r"^H\s*","",p[5],flags=re.I)),"trainer":_name(p[6]),"trat":_f(re.sub(r"^H\s*","",p[7],flags=re.I)),"tab_odds":999.0 if scr else odds,"scratched":scr})
    return out


def parse_summary_table(raw: str) -> list[dict[str, Any]]:
    rows = _summary_markdown(raw) or _summary_plain(raw); seen=set(); out=[]
    for r in rows:
        if r["tab"] not in seen: out.append(r); seen.add(r["tab"])
    return out


def _form_price(text: str):
    ms=list(re.finditer(r"(?i)(?<![A-Za-z0-9])([0-9xXfF]{1,10})\s+\$([0-9]+(?:\.\d+)?)", text))
    return ms[-1] if ms else None


def _split_detail_blocks(raw: str, runners: list[dict[str, Any]]) -> dict[int, str]:
    t=_clean(raw); starts=[]
    for r in runners:
        ms=list(re.finditer(rf"(?mi)^\s*{re.escape(r['horse'])}\s+(\d+)yo\b[^\n]*$", t))
        if ms: starts.append((ms[0].start(),r["tab"]))
    starts.sort(); out={}
    for i,(pos,tab) in enumerate(starts):
        end=starts[i+1][0] if i+1<len(starts) else len(t); ps=max(0,pos-260); prefix=t[ps:pos]; pair=_form_price(prefix); start=ps+(pair.start() if pair else 0); out[tab]=t[start:end]
    return out


def _after(block: str, label: str) -> str:
    lines=[x.strip() for x in block.splitlines()]; target=label.lower()
    for i,x in enumerate(lines[:-1]):
        if x.lower()==target:
            for j in range(i+1,min(i+5,len(lines))):
                if lines[j]: return lines[j]
    return ""


def _record(v: str):
    s=re.sub(r"\s+","",v or ""); m=re.fullmatch(r"(\d+)-(\d+)-(\d+)",s)
    if m:
        w,p,st=map(int,m.groups()); den=max(st,1); return s,w,p,st,w/den,(w+p)/den
    m=re.fullmatch(r"(\d+(?:\.\d+)?)%-(\d+(?:\.\d+)?)%-(\d+)",s)
    if m:
        wp,tp,st=float(m.group(1)),float(m.group(2)),int(m.group(3)); w=int(round(st*wp/100)); top=int(round(st*tp/100)); return s,w,max(top-w,0),st,wp/100,tp/100
    return "0-0-0",0,0,0,0.0,0.0


def _records(block: str):
    labels=["Car","12m","Crs","Dist","Crs & Dist","Firm","Good","Soft","Heavy","AW","Turf","G1","G2","G3","LR","FU","2U","3U","ClockW","AClockW","Dirt","Sand"]
    m=re.search(r"(?is)\bFilters\b(.*?)\bFacts\b",block); seg=m.group(1) if m else block; pos=[]; cur=0
    for label in labels:
        lm=re.search(rf"(?i)(?<!\w){re.escape(label)}(?!\w)",seg[cur:])
        if lm:
            a=cur+lm.start(); b=cur+lm.end(); pos.append((a,label,b)); cur=b
    out={}
    for i,(_,label,b) in enumerate(pos):
        stop=pos[i+1][0] if i+1<len(pos) else len(seg); tm=re.search(r"\d+(?:\.\d+)?%?-\d+(?:\.\d+)?%?-\d+",seg[b:stop]); out[label]=_record(tm.group(0) if tm else "")
    return out


def _prev(lines, idx, floor):
    j=idx-1
    while j>=floor and not lines[j]: j-=1
    return lines[j] if j>=floor else ""


def _recent(block: str) -> list[dict[str, Any]]:
    lines=[x.strip().replace("\t"," ") for x in block.splitlines()]; out=[]
    for i,line in enumerate(lines):
        if "Margin" not in line or "Distance" not in line or "Race Time" not in line or "Trial Time" in line: continue
        r={}; floor=max(0,i-24)
        for j in range(floor,i):
            fm=re.fullmatch(r"(\d+)\s+of\s+(\d+)",lines[j],re.I)
            if fm: r["finish"],r["field"]=int(fm.group(1)),int(fm.group(2))
            if lines[j].upper()=="OHR":
                pv=_prev(lines,j,floor)
                if re.fullmatch(r"\d{1,3}",pv): r["ohr"]=int(pv)
        for key,pat,typ in (("margin",r"\bMargin\s*([\d.]+)L",float),("distance",r"\bDistance\s*(\d+)m",int),("sp",r"\bSP\s*\$([\d.]+)",float),("weight",r"\bWeight\s*([\d.]+)",float),("prior_box",r"\bBP\s*(\d+)",int),("sec_time",r"\bSec Time\s*([\d.]+)",float)):
            sm=re.search(pat,line,re.I)
            if sm: r[key]=typ(sm.group(1))
        sm=re.search(r"\bClass\s*(.*?)\s*Prize\b",line,re.I)
        if sm:r["class"]=sm.group(1).strip()
        sm=re.search(r"\bGear Change\s*(.*?)(?=\s*Stewards|\s*Inrunning Position|\s*Tempo|\s*Race/Horse Sectionals:|\s*Video Comments|$)",line,re.I)
        if sm:r["gear_change"]=sm.group(1).strip()
        sm=re.search(r"\bStewards\s*(.*?)(?=\s*Inrunning Position|\s*Tempo|\s*Race/Horse Sectionals:|\s*Video Comments|$)",line,re.I)
        if sm:r["stewards"]=sm.group(1).strip().rstrip(".")
        out.append(r)
    return out


def _parse_block(block: str, runner: dict[str, Any]) -> dict[str, Any]:
    d={}; pair=_form_price(block[:400])
    if pair: d["form5"],d["bf_odds"]=pair.group(1).lower(),_f(pair.group(2),999.0)
    m=re.search(rf"(?mi)^\s*{re.escape(runner['horse'])}\s+(\d+)yo\s+([A-Z/]+)\s+([A-Za-z]+)\b",block)
    if m:d["age"],d["colour"],d["sex"]=int(m.group(1)),m.group(2),m.group(3)
    sire=_after(block,"Sire")
    if sire:d["sire"]=sire
    js=re.search(r"(?is)\bJockey\b(.*?)\bTrainer\b",block); ts=re.search(r"(?is)\bTrainer\b(.*?)(?:\bRaced Dist\.|\bJ/H\b)",block)
    if js:
        m=re.search(r"Last50\s*(\d+)%-(\d+)%-(\d+)",js.group(1),re.I)
        if m:d["jky_win"],d["jky_place"]=int(m.group(1))/100,int(m.group(2))/100
    if ts:
        m=re.search(r"Last50\s*(\d+)%-(\d+)%-(\d+)",ts.group(1),re.I)
        if m:d["trn_win"],d["trn_place"]=int(m.group(1))/100,int(m.group(2))/100
    l50=re.findall(r"Last50\s*(\d+)%-(\d+)%-(\d+)",block,re.I)
    if l50 and "jky_win" not in d:d["jky_win"],d["jky_place"]=int(l50[0][0])/100,int(l50[0][1])/100
    if len(l50)>1 and "trn_win" not in d:d["trn_win"],d["trn_place"]=int(l50[1][0])/100,int(l50[1][1])/100
    m=re.search(r"(?is)(?<!\w)J/T(?!\w)\s*(\d+)%-(\d+)%-(\d+)",block)
    if m:d["jt_win"],d["jt_runs"]=int(m.group(1))/100,int(m.group(3))
    km={"Car":"Car","12m":"12m","Crs":"Crs","Dist":"Dist","Crs & Dist":"CrsDist","Firm":"Firm","Good":"Good","Soft":"Soft","Heavy":"Heavy","AW":"AW","Turf":"Turf","FU":"FU","2U":"2U","3U":"3U","ClockW":"ClockW","AClockW":"AClockW"}
    for label,rec in _records(block).items():
        if label not in km:continue
        key=km[label]; disp,_,_,st,wr,pr=rec; d[f"{key}_rec"],d[f"{key}_win"],d[f"{key}_plc"],d[f"{key}_starts"]=disp,wr,pr,st
    fm=re.search(r"(?is)\bFacts\b(.*?)(?:Days Since Last Run:|\Z)",block); fs=fm.group(1) if fm else block
    m=re.search(r"\bDLS\b\s*(\d+)",fs,re.I)
    if m:d["dslr"]=int(m.group(1))
    m=re.search(r"Days Since Last Run:\s*(\d+)\s*days(?:\s*\((\d+)U\))?",block,re.I)
    if m:
        d["dslr"]=int(m.group(1));
        if m.group(2):d["runs_this_prep"]=int(m.group(2))
    if "runs_this_prep" not in d:
        m=re.search(r"\bRTC/km\b\s*(\d+)",fs,re.I)
        if m:d["runs_this_prep"]=int(m.group(1))
    m=re.search(r"\bCar PM\b\s*\$([\d,.]+)\s*([kKmM]?)",fs,re.I)
    if m:
        val=float(m.group(1).replace(",","")); unit=m.group(2).lower(); d["career_pm_k"]=val*1000 if unit=="m" else val if unit=="k" else val/1000
    m=re.search(r"\b12m PM\b\s*\$([\d,.]+)\s*([kKmM]?)",fs,re.I)
    if m:
        val=float(m.group(1).replace(",","")); unit=m.group(2).lower(); d["pm_12m"]=val*1_000_000 if unit=="m" else val*1000 if unit=="k" else val
    d["recent_runs"]=_recent(block)
    if d["recent_runs"]:
        last=d["recent_runs"][0]
        for s,t in (("finish","last_fin"),("ohr","ohr"),("margin","ls_margin"),("distance","ls_dist"),("class","ls_class"),("sp","ls_sp")):
            if s in last:d[t]=last[s]
        d["gear_change"]=bool(last.get("gear_change"))
    ratings=[x["ohr"] for x in d["recent_runs"] if x.get("ohr")]
    if "ohr" not in d and ratings:d["ohr"]=ratings[0]
    if "last_fin" not in d and d.get("form5"):
        digits=re.sub(r"\D","",d["form5"])
        if digits:d["last_fin"]=10 if digits[-1]=="0" else int(digits[-1])
    d.setdefault("gear_change",False); d["had_trial"]=bool(re.search(r"(?mi)^BT\s*$|BT Results",block)); return d


def parse(raw: str):
    warnings=[]; header=parse_race_header(raw); runners=parse_summary_table(raw)
    if not runners:return header,[],["Could not locate runners summary table."]
    blocks=_split_detail_blocks(raw,runners)
    for r in runners:
        if r["tab"] in blocks:r.update(_parse_block(blocks[r["tab"]],r))
        else:warnings.append(f"No detail block found for #{r['tab']} {r['horse']}.")
        r.setdefault("bf_odds",r.get("tab_odds",999.0)); r.setdefault("ohr",0); r.setdefault("dslr",30); r.setdefault("runs_this_prep",1); r.setdefault("last_fin",10); r.setdefault("jky_win",.05); r.setdefault("trn_win",.05); r.setdefault("jt_win",0.0)
        for key in ("Car","12m","Crs","Dist","CrsDist","Good","Soft","Heavy"):
            r.setdefault(f"{key}_rec","0-0-0"); r.setdefault(f"{key}_win",0.0); r.setdefault(f"{key}_plc",0.0); r.setdefault(f"{key}_starts",0)
        for key,val in (("form5",""),("career_pm_k",0.0),("pm_12m",0.0),("ls_margin",0.0),("ls_dist",0),("ls_class",""),("ls_sp",0.0),("gear_change",False),("had_trial",False)):r.setdefault(key,val)
    active=[r for r in runners if not r.get("scratched")]
    if any(r["tab"] not in blocks for r in active):warnings.append("Detailed form was not parsed for one or more active runners.")
    if any(r.get("ohr",0)==0 for r in active):warnings.append("One or more active runners have no parsed OHR.")
    return header,runners,warnings
