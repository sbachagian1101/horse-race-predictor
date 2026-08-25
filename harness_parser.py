"""Robust Racing & Sports harness Enhanced Form paste parser."""
from __future__ import annotations

import re
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        s=str(value).replace("$","").replace(",","").replace("%","").strip(); mult=1.0
        if s.lower().endswith("k"): mult,s=1000.0,s[:-1]
        elif s.lower().endswith("m"): mult,s=1_000_000.0,s[:-1]
        return float(s)*mult
    except Exception:return default


def _time(value: Any, default: float = 0.0) -> float:
    try:
        s=str(value).strip()
        if ":" not in s:return float(s)
        p=s.split(":")
        return 60*float(p[0])+float(p[1]) if len(p)==2 else 3600*float(p[0])+60*float(p[1])+float(p[2])
    except Exception:return default


def _name(v: str) -> str:return re.sub(r"\s+"," ",str(v or "")).strip().upper()


def _clean(text: str) -> str:
    text=str(text or "").replace("\xa0"," ").replace("\u2003"," ").replace("\u2002"," ").replace("\u202f"," ")
    text=text.replace("\\-","-").replace("\\:",":").replace("\\&","&")
    text=re.sub(r"\[([^\]]+)\]\([^\n]*?\)",r"\1",text).replace("***","").replace("**","").replace("__","")
    text=re.sub(r"^[#>*]+\s*","",text,flags=re.M); text=re.sub(r"^\s*[-*]\s+(?=[A-Za-z\[])","",text,flags=re.M)
    return "\n".join(x.strip() for x in text.splitlines())


def _link(c: str) -> str:
    m=re.search(r"\[\**([^\]]+?)\**\]\(",c); return (m.group(1) if m else re.sub(r"[\[\]*]","",c)).strip()


def parse_header(raw: str) -> dict[str,Any]:
    t=_clean(raw); h={}
    m=re.search(r"(?mi)^(.+?)\s+Form Guide\s*\(Race\s*(\d+)\)",t)
    if m:h["track"],h["race_no"]=m.group(1).strip(),int(m.group(2))
    m=re.search(r"(?mi)^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(.+?\d{4})$",t)
    if m:h["date"]=f"{m.group(1)}, {m.group(2)}"
    m=re.search(r"(?m)^(\d{1,2}:\d{2})\s*$",t)
    if m:h["time"]=m.group(1)
    m=re.search(r"(?is)\(local\)\s*\n+\s*([^\n]+?)\s*\n+\s*(?:Age:|Fastest Time:)",t)
    if m:h["race_name"]=m.group(1).strip()
    m=re.search(r"(?i)Fastest Time:\s*([0-9:.]+)",t)
    if m:h["fastest_time"]=m.group(1)
    m=re.search(r"AUD\s*\$([\d,]+)",t,re.I)
    if m:h["prize"]=f"AUD ${m.group(1)}"
    m=re.search(r"(?mi)^(\d{3,4})m\s+([A-Z ]+?)\s+(FAST|GOOD|SLOW|WET|HEAVY)\s*$",t)
    if m:h["distance_m"],h["surface"],h["going"]=int(m.group(1)),m.group(2).strip().upper(),m.group(3).upper()
    return h


def _summary_markdown(raw: str) -> list[dict[str,Any]]:
    out=[]
    for line in raw.splitlines():
        if not re.match(r"^\|\s*\d{1,2}\s*\|",line.strip()):continue
        c=[x.strip() for x in line.strip().strip("|").split("|")]
        if len(c)<8 or not re.search(r"\$",c[2]):continue
        n=re.sub(r"\D","",c[0])
        if not n:continue
        tab=int(n); scr=any(re.search(r"\bscr\b",x,re.I) for x in c); odds=999.0
        for x in reversed(c):
            x2=re.sub(r"[*$]","",x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?",x2):odds=_f(x2,999.0);break
        out.append({"tab":tab,"gate":tab,"horse":_name(_link(c[1])),"driver":_name(_link(c[4])) if len(c)>4 else "","trainer":_name(_link(c[7])) if len(c)>7 else "","total_pm":_f(c[2]) if len(c)>2 else 0,"pm_per_start":_f(c[3]) if len(c)>3 else 0,"driver_l50_pm":_f(c[5]) if len(c)>5 else 0,"driver_total_pm":_f(c[6]) if len(c)>6 else 0,"trainer_l50_pm":_f(c[8]) if len(c)>8 else 0,"trainer_total_pm":_f(c[9]) if len(c)>9 else 0,"scratched":scr,"tab_odds":999.0 if scr else odds})
    return out


def _summary_plain(raw: str) -> list[dict[str,Any]]:
    out=[]
    for line in _clean(raw).splitlines():
        p=[x.strip() for x in line.split("\t") if x.strip()]
        if len(p)<8 or not re.fullmatch(r"\d{1,2}",p[0]) or not re.search(r"[A-Za-z]",p[1]):continue
        tab=int(p[0]);scr=any(re.search(r"\bscr\b",x,re.I) for x in p);odds=999.0
        for x in reversed(p):
            x2=re.sub(r"[$*]","",x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?",x2):odds=_f(x2,999.0);break
        out.append({"tab":tab,"gate":tab,"horse":_name(p[1]),"driver":_name(p[4]) if len(p)>4 else "","trainer":_name(p[7]) if len(p)>7 else "","scratched":scr,"tab_odds":999.0 if scr else odds})
    return out


def parse_summary(raw: str) -> list[dict[str,Any]]:
    rows=_summary_markdown(raw) or _summary_plain(raw);seen=set();out=[]
    for r in rows:
        if r["tab"] not in seen:out.append(r);seen.add(r["tab"])
    return out


def _form_price(t: str):
    ms=list(re.finditer(r"(?i)(?<![A-Za-z0-9])([0-9xXfF]{1,10})\s+\$([0-9]+(?:\.\d+)?)",t));return ms[-1] if ms else None


def _runner_blocks(raw: str,runners: list[dict[str,Any]]) -> dict[int,str]:
    t=_clean(raw);starts=[]
    for r in runners:
        ms=list(re.finditer(rf"(?mi)^\s*{re.escape(r['horse'])}\s+(\d+)yo\b[^\n]*$",t))
        if ms:starts.append((ms[0].start(),r["tab"]))
    starts.sort();out={}
    for i,(pos,tab) in enumerate(starts):
        end=starts[i+1][0] if i+1<len(starts) else len(t);ps=max(0,pos-260);prefix=t[ps:pos];pair=_form_price(prefix);start=ps+(pair.start() if pair else 0);out[tab]=t[start:end]
    return out


def _record(v: str):
    s=re.sub(r"\s+","",v or "");m=re.fullmatch(r"(\d+)-(\d+)-(\d+)",s)
    if m:return s,int(m.group(1)),int(m.group(2)),int(m.group(3))
    m=re.fullmatch(r"(\d+(?:\.\d+)?)%-(\d+(?:\.\d+)?)%-(\d+)",s)
    if m:
        wp,tp,st=float(m.group(1)),float(m.group(2)),int(m.group(3));w=int(round(st*wp/100));top=int(round(st*tp/100));return s,w,max(top-w,0),st
    return "0-0-0",0,0,0


def _records(block: str):
    labels=["Car","12m","Crs","Dist","Crs & Dist","AW","Turf","G1","G2","G3","LR","FU","2U","3U","ClockW","AClockW","Dirt","Sand"]
    m=re.search(r"(?is)\bFilters\b(.*?)\bFacts\b",block);seg=m.group(1) if m else block;pos=[];cur=0
    for label in labels:
        lm=re.search(rf"(?i)(?<!\w){re.escape(label)}(?!\w)",seg[cur:])
        if lm:
            a=cur+lm.start();b=cur+lm.end();pos.append((a,label,b));cur=b
    out={}
    for i,(_,label,b) in enumerate(pos):
        stop=pos[i+1][0] if i+1<len(pos) else len(seg);tm=re.search(r"\d+(?:\.\d+)?%?-\d+(?:\.\d+)?%?-\d+",seg[b:stop]);out[label]=_record(tm.group(0) if tm else "")
    return out


def _prev(lines,idx,floor):
    j=idx-1
    while j>=floor and not lines[j]:j-=1
    return lines[j] if j>=floor else ""


def _recent(block: str) -> list[dict[str,Any]]:
    lines=[x.strip().replace("\t"," ") for x in block.splitlines()];out=[]
    for i,line in enumerate(lines):
        if "Margin" not in line or "Distance" not in line or "Race Mile Rate" not in line or "Trial Time" in line:continue
        r={};floor=max(0,i-24)
        for j in range(floor,i):
            fm=re.fullmatch(r"(\d+)\s+of\s+(\d+)",lines[j],re.I)
            if fm:r["finish"],r["field"]=int(fm.group(1)),int(fm.group(2))
            im=re.fullmatch(r"(\d+)(?:st|nd|rd|th)\s+([0-9]+:[0-9.]+)",lines[j],re.I)
            if im:r["imr_rank"],r["imr"]=int(im.group(1)),_time(im.group(2))
            if lines[j].upper()=="OHR":
                pv=_prev(lines,j,floor)
                if re.fullmatch(r"\d{1,3}",pv):r["ohr"]=int(pv)
        for key,pat in (("margin",r"\bMargin\s*([\d.]+)L"),("distance",r"\bDistance\s*(\d+)m"),("race_mile_rate",r"\bRace Mile Rate\s*([0-9]+:[0-9.]+)"),("mile_rate_adj",r"\bRace Mile Rate Adj\s*([+-]?\d+(?:\.\d+)?)"),("sp",r"\bSP\s*\$([\d.]+)")):
            sm=re.search(pat,line,re.I)
            if sm:r[key]=int(sm.group(1)) if key=="distance" else _time(sm.group(1)) if key=="race_mile_rate" else _f(sm.group(1))
        hm=re.search(r"\bHCP\s*([A-Za-z]+\d+)",line,re.I)
        if hm:
            r["hcp"]=hm.group(1).upper();gm=re.search(r"(\d+)$",r["hcp"]);r["prior_gate"]=int(gm.group(1)) if gm else 0;r["second_row"]=r["hcp"].startswith("SR")
        cm=re.search(r"\bClass\s*(.*?)\s*Prize\b",line,re.I)
        if cm:r["class"]=cm.group(1).strip()
        sm=re.search(r"\bStewards\s*(.*?)(?=\s*Inrunning Position|\s*Race/Horse Sectionals:|$)",line,re.I)
        if sm:r["stewards"]=sm.group(1).strip().rstrip(".")
        for key,pat in (("settle_pos",r"Inrunning Position\s*(\d+)(?:st|nd|rd|th) Place on settling"),("pos1200",r"(\d+)(?:st|nd|rd|th) Place at 1200m"),("pos800",r"(\d+)(?:st|nd|rd|th) Place at 800m"),("bell_pos",r"(\d+)(?:st|nd|rd|th) position at Bell Lap")):
            pm=re.search(pat,line,re.I)
            if pm:r[key]=int(pm.group(1))
        sm=re.search(r"L800m\s*\(R:\s*[\d.]+\)\s*\(H:\s*([\d.]+)",line,re.I)
        if sm:r["l800"]=_f(sm.group(1))
        else:
            sm=re.search(r"L800m\s*\(([\d.]+)\)",line,re.I)
            if sm:r["l800"]=_f(sm.group(1))
        sm=re.search(r"L400m\s*\(R:\s*[\d.]+\)\s*\(H:\s*([\d.]+)",line,re.I)
        if sm:r["l400"]=_f(sm.group(1))
        else:
            sm=re.search(r"L400m\s*\(([\d.]+)\)",line,re.I)
            if sm:r["l400"]=_f(sm.group(1))
        dm=re.search(r"(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})",line)
        if dm:r["date"]=dm.group(1)
        tm=re.search(r"([A-Za-z .'-]+)\s*\(AUSTRALIA\):",line,re.I)
        if tm:r["track"]=tm.group(1).strip().upper()
        out.append(r)
    return out


def _parse_block(block: str,runner: dict[str,Any]) -> dict[str,Any]:
    d={};pair=_form_price(block[:400])
    if pair:d["form"],d["bf_odds"]=pair.group(1).lower(),_f(pair.group(2),999.0)
    m=re.search(rf"(?mi)^\s*{re.escape(runner['horse'])}\s+(\d+)yo\s+([A-Z/]+)\s+([A-Za-z]+)\b",block)
    if m:d["age"],d["colour"],d["sex"]=int(m.group(1)),m.group(2),m.group(3).upper()
    ds=re.search(r"(?is)\bDriver\b(.*?)\bTrainer\b",block);ts=re.search(r"(?is)\bTrainer\b(.*?)(?:\bRaced Dist\.|\bD/H\b)",block)
    if ds:
        lm=re.search(r"Last50\s*(\d+)%-(\d+)%-(\d+)",ds.group(1),re.I)
        if lm:d["driver_win"],d["driver_place"],d["driver_l50_n"]=int(lm.group(1))/100,int(lm.group(2))/100,int(lm.group(3))
    if ts:
        lm=re.search(r"Last50\s*(\d+)%-(\d+)%-(\d+)",ts.group(1),re.I)
        if lm:d["trainer_win"],d["trainer_place"],d["trainer_l50_n"]=int(lm.group(1))/100,int(lm.group(2))/100,int(lm.group(3))
    l50=re.findall(r"Last50\s*(\d+)%-(\d+)%-(\d+)",block,re.I)
    if l50 and "driver_win" not in d:d["driver_win"],d["driver_place"],d["driver_l50_n"]=int(l50[0][0])/100,int(l50[0][1])/100,int(l50[0][2])
    if len(l50)>1 and "trainer_win" not in d:d["trainer_win"],d["trainer_place"],d["trainer_l50_n"]=int(l50[1][0])/100,int(l50[1][1])/100,int(l50[1][2])
    for label,prefix in (("D/H","driver_horse"),("D/T","driver_trainer")):
        lm=re.search(rf"(?is)(?<!\w){re.escape(label)}(?!\w)\s*(\d+)%-(\d+)%-(\d+)",block)
        if lm:d[f"{prefix}_win"],d[f"{prefix}_place"],d[f"{prefix}_n"]=int(lm.group(1))/100,int(lm.group(2))/100,int(lm.group(3))
    rm=re.search(r"(?is)\bRaced Dist\.\s*(\d+)m\s*-\s*(\d+)m",block)
    if rm:d["raced_dist_min"],d["raced_dist_max"]=int(rm.group(1)),int(rm.group(2))
    km={"Car":"career","12m":"12m","Crs":"course","Dist":"distance","Crs & Dist":"course_distance","FU":"fu","2U":"2u","3U":"3u","ClockW":"clockwise","AClockW":"anticlockwise"}
    for label,rec in _records(block).items():
        if label not in km:continue
        key=km[label];disp,w,p,st=rec;d[f"{key}_rec"],d[f"{key}_wins"],d[f"{key}_places"],d[f"{key}_starts"]=disp,w,p,st
    fm=re.search(r"(?is)\bFacts\b(.*?)(?:Days Since Last Run:|\Z)",block);fs=fm.group(1) if fm else block
    m=re.search(r"\bDLS\b\s*(\d+)",fs,re.I)
    if m:d["dls"]=int(m.group(1))
    m=re.search(r"\bDLW\b\s*(\d+)",fs,re.I)
    if m:d["dlw"]=int(m.group(1))
    m=re.search(r"\bROI\b\s*([\d.]+)%",fs,re.I)
    if m:d["roi"]=_f(m.group(1))/100
    d["recent_runs"]=_recent(block);ratings=[x["ohr"] for x in d["recent_runs"] if x.get("ohr")]
    if ratings:d["latest_ohr"]=ratings[0]
    return d


def parse(raw: str):
    warnings=[];header=parse_header(raw);runners=parse_summary(raw)
    if not runners:return header,[],["Could not locate the harness runners table."]
    blocks=_runner_blocks(raw,runners)
    for r in runners:
        if r["tab"] in blocks:r.update(_parse_block(blocks[r["tab"]],r))
        else:warnings.append(f"No detail block found for #{r['tab']} {r['horse']}.")
        for k,v in (("form",""),("driver_win",.10),("driver_place",.32),("trainer_win",.10),("trainer_place",.32),("driver_horse_win",0.0),("driver_horse_place",0.0),("driver_horse_n",0),("driver_trainer_win",0.0),("driver_trainer_place",0.0),("driver_trainer_n",0),("dls",14),("recent_runs",[])):r.setdefault(k,v)
        for key in ("career","12m","course","distance","course_distance"):
            r.setdefault(f"{key}_rec","0-0-0");r.setdefault(f"{key}_wins",0);r.setdefault(f"{key}_places",0);r.setdefault(f"{key}_starts",0)
    active=[r for r in runners if not r.get("scratched")]
    if any(r["tab"] not in blocks for r in active):warnings.append("Detailed form was not parsed for one or more active runners.")
    if any(len(r.get("recent_runs",[]))<3 for r in active):warnings.append("Some active runners have fewer than three parsed recent starts; confidence is reduced.")
    if not header.get("distance_m"):warnings.append("Race distance was not parsed; distance matching will be limited.")
    return header,runners,warnings
