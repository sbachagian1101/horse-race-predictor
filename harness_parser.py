"""Racing & Sports harness Enhanced Form parser."""
from __future__ import annotations
import re
from typing import Any

def _f(v:Any,default:float=0.0)->float:
    try:
        s=str(v).replace("$","").replace(",","").replace("%","").strip(); mult=1
        if s.lower().endswith("k"):mult=1000;s=s[:-1]
        elif s.lower().endswith("m"):mult=1_000_000;s=s[:-1]
        return float(s)*mult
    except:return default
def _time(v:Any,default=0.0):
    try:
        s=str(v).strip()
        if ":" not in s:return float(s)
        a=s.split(":");return 60*float(a[0])+float(a[1])
    except:return default
def _name(v):return re.sub(r"\s+"," ",str(v or "")).strip().upper()
def _clean(text):
    text=str(text or "").replace("\xa0"," ").replace("\u2003"," ").replace("\u2002"," ").replace("\u202f"," ")
    text=text.replace("\\-","-").replace("\\:",":").replace("\\&","&")
    text=re.sub(r"\[([^\]]+)\]\([^\n]*?\)",r"\1",text).replace("***","").replace("**","").replace("__","")
    text=re.sub(r"^[#>*]+\s*","",text,flags=re.M);text=re.sub(r"^\s*[-*]\s+(?=[A-Za-z\[])","",text,flags=re.M)
    return "\n".join(x.strip() for x in text.splitlines())
def _link(c):
    m=re.search(r"\[\**([^\]]+?)\**\]\(",c);return (m.group(1) if m else re.sub(r"[\[\]*]","",c)).strip()
def _after(block,label):
    ls=[x.strip() for x in block.splitlines()]
    for i,x in enumerate(ls[:-1]):
        if x.lower()==label.lower():
            for y in ls[i+1:i+5]:
                if y:return y
    return ""
def _record(v):
    s=re.sub(r"\s+","",v or "");m=re.fullmatch(r"(\d+)-(\d+)-(\d+)",s)
    if m:return s,*map(int,m.groups())
    m=re.fullmatch(r"(\d+(?:\.\d+)?)%-(\d+(?:\.\d+)?)%-(\d+)",s)
    if m:
        wp,tp,n=float(m.group(1)),float(m.group(2)),int(m.group(3));w=round(n*wp/100);top=round(n*tp/100)
        return s,int(w),max(int(top-w),0),n
    return "0-0-0",0,0,0

def parse_header(raw):
    t=_clean(raw);h={}
    m=re.search(r"(?mi)^(.+?)\s+Form Guide\s*\(Race\s*(\d+)\)",t)
    if m:h["track"],h["race_no"]=m.group(1).strip(),int(m.group(2))
    m=re.search(r"(?mi)^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(.+?\d{4})$",t)
    if m:h["date"]=f"{m.group(1)}, {m.group(2)}"
    m=re.search(r"(?is)\(local\)\s*\n+\s*([^\n]+?)\s*\n+\s*(?:Age:|Fastest Time:)",t)
    if m:h["race_name"]=m.group(1).strip()
    m=re.search(r"AUD\s*\$([\d,]+)",t,re.I)
    if m:h["prize"]=f"AUD ${m.group(1)}"
    m=re.search(r"(?mi)^(\d{3,4})m\s+([A-Z ]+?)\s+(FAST|GOOD|SLOW|WET|HEAVY)\s*$",t)
    if m:h["distance_m"],h["surface"],h["going"]=int(m.group(1)),m.group(2).strip().upper(),m.group(3).upper()
    return h

def parse_summary(raw):
    out=[]
    for line in raw.splitlines():
        if not re.match(r"^\|\s*\d{1,2}\s*\|",line.strip()):continue
        c=[x.strip() for x in line.strip().strip("|").split("|")]
        if len(c)<8 or not re.search(r"\$",c[2]):continue
        tab=int(re.sub(r"\D","",c[0]));scr=any(re.search(r"\bscr\b",x,re.I) for x in c);odds=999.
        for x in reversed(c):
            z=re.sub(r"[*$]","",x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?",z):odds=_f(z,999);break
        out.append({"tab":tab,"gate":tab,"horse":_name(_link(c[1])),"driver":_name(_link(c[4])),"trainer":_name(_link(c[7])),"scratched":scr,"tab_odds":999 if scr else odds,"total_pm":_f(c[2]),"pm_per_start":_f(c[3])})
    seen=set();clean=[]
    for r in out:
        if r["tab"] not in seen:clean.append(r);seen.add(r["tab"])
    return clean

def _blocks(raw,runners):
    t=_clean(raw);starts=[]
    for r in runners:
        m=re.search(rf"(?mi)^\s*{re.escape(r['horse'])}\s+(\d+)yo\b[^\n]*$",t)
        if m:starts.append((m.start(),r["tab"]))
    starts.sort();out={}
    for i,(pos,tab) in enumerate(starts):
        end=starts[i+1][0] if i+1<len(starts) else len(t);ps=max(0,pos-320);pref=t[ps:pos]
        pairs=list(re.finditer(r"(?mi)^\s*([0-9xXfF]{1,10})\s*$\s*^\s*\$([0-9]+(?:\.\d+)?)\s*$",pref))
        out[tab]=t[ps+(pairs[-1].start() if pairs else 0):end]
    return out

def _recent(block):
    ls=[x.strip() for x in block.splitlines()];out=[]
    for i,line in enumerate(ls):
        if "Margin" not in line or "Distance" not in line or "Race Mile Rate" not in line or "Trial Time" in line:continue
        r={};floor=max(0,i-30)
        for j in range(floor,i):
            m=re.fullmatch(r"(\d+)\s+of\s+(\d+)",ls[j],re.I)
            if m:r["finish"],r["field"]=int(m.group(1)),int(m.group(2))
            m=re.fullmatch(r"(\d+)(?:st|nd|rd|th)\s+([0-9]+:[0-9.]+)",ls[j],re.I)
            if m:r["imr_rank"],r["imr"]=int(m.group(1)),_time(m.group(2))
            if ls[j].upper()=="OHR":
                k=j-1
                while k>=floor and not ls[k]:k-=1
                if k>=floor and re.fullmatch(r"\d{1,3}",ls[k]):r["ohr"]=int(ls[k])
        for key,pat in [("margin",r"\bMargin\s*([\d.]+)L"),("distance",r"\bDistance\s*(\d+)m"),("mile_rate_adj",r"\bRace Mile Rate Adj\s*([+-]?\d+(?:\.\d+)?)"),("sp",r"\bSP\s*\$([\d.]+)")]:
            m=re.search(pat,line,re.I)
            if m:r[key]=int(m.group(1)) if key=="distance" else _f(m.group(1))
        m=re.search(r"\bRace Mile Rate\s*([0-9]+:[0-9.]+)",line,re.I)
        if m:r["race_mile_rate"]=_time(m.group(1))
        m=re.search(r"\bHCP\s*([A-Za-z]+\d+)",line,re.I)
        if m:
            r["hcp"]=m.group(1).upper();g=re.search(r"(\d+)$",r["hcp"]);r["prior_gate"]=int(g.group(1)) if g else 0;r["second_row"]=r["hcp"].startswith("SR")
        m=re.search(r"\bClass\s*(.*?)\s*Prize\b",line,re.I)
        if m:r["class"]=m.group(1).strip()
        m=re.search(r"\bStewards\s*(.*?)(?=\s*Inrunning Position|\s*Race/Horse Sectionals:|$)",line,re.I)
        if m:r["stewards"]=m.group(1).strip()
        for key,pat in [("settle_pos",r"Inrunning Position\s*(\d+)(?:st|nd|rd|th) Place on settling"),("pos1200",r"(\d+)(?:st|nd|rd|th) Place at 1200m"),("pos800",r"(\d+)(?:st|nd|rd|th) Place at 800m"),("bell_pos",r"(\d+)(?:st|nd|rd|th) position at Bell Lap")]:
            m=re.search(pat,line,re.I)
            if m:r[key]=int(m.group(1))
        for key,pat in [("l800",r"L800m\s*\(R:\s*[\d.]+\)\s*\(H:\s*([\d.]+)"),("l400",r"L400m\s*\(R:\s*[\d.]+\)\s*\(H:\s*([\d.]+)")]:
            m=re.search(pat,line,re.I)
            if m:r[key]=_f(m.group(1))
        if "l800" not in r:
            m=re.search(r"L800m\s*\(([\d.]+)\)",line,re.I)
            if m:r["l800"]=_f(m.group(1))
        if "l400" not in r:
            m=re.search(r"L400m\s*\(([\d.]+)\)",line,re.I)
            if m:r["l400"]=_f(m.group(1))
        out.append(r)
    return out

def _parse_block(block,runner):
    d={}
    m=re.search(r"(?mi)^\s*([0-9xXfF]{1,10})\s*$\s*^\s*\$([0-9]+(?:\.\d+)?)\s*$",block[:450])
    if m:d["form"],d["bf_odds"]=m.group(1).lower(),_f(m.group(2),999)
    m=re.search(rf"(?mi)^\s*{re.escape(runner['horse'])}\s+(\d+)yo\s+([A-Z/]+)\s+([A-Za-z]+)\b",block)
    if m:d["age"],d["colour"],d["sex"]=int(m.group(1)),m.group(2),m.group(3).upper()
    l50=re.findall(r"(?mi)^Last50\s*$\s*^(\d+)%-(\d+)%-(\d+)\s*$",block)
    if l50:d["driver_win"],d["driver_place"],d["driver_l50_n"]=int(l50[0][0])/100,int(l50[0][1])/100,int(l50[0][2])
    if len(l50)>1:d["trainer_win"],d["trainer_place"],d["trainer_l50_n"]=int(l50[1][0])/100,int(l50[1][1])/100,int(l50[1][2])
    for lab,prefix in [("D/H","driver_horse"),("D/T","driver_trainer")]:
        rec=_record(_after(block,lab));n=rec[3]
        if "%" in rec[0]:
            a=re.match(r"([\d.]+)%-([\d.]+)%",rec[0]);d[f"{prefix}_win"]=float(a.group(1))/100;d[f"{prefix}_place"]=float(a.group(2))/100
        else:
            d[f"{prefix}_win"]=rec[1]/max(n,1);d[f"{prefix}_place"]=(rec[1]+rec[2])/max(n,1)
        d[f"{prefix}_n"]=n
    mapping={"Car":"career","12m":"12m","Crs":"course","Dist":"distance","Crs & Dist":"course_distance"}
    for lab,key in mapping.items():
        disp,w,p,n=_record(_after(block,lab));d[f"{key}_rec"]=disp;d[f"{key}_wins"]=w;d[f"{key}_places"]=p;d[f"{key}_starts"]=n
    x=_after(block,"DLS");m=re.search(r"\d+",x)
    if m:d["dls"]=int(m.group())
    x=_after(block,"DLW");m=re.search(r"\d+",x)
    if m:d["dlw"]=int(m.group())
    x=_after(block,"ROI");m=re.search(r"[\d.]+",x)
    if m:d["roi"]=_f(m.group())/100
    d["recent_runs"]=_recent(block);ratings=[x["ohr"] for x in d["recent_runs"] if x.get("ohr")]
    if ratings:d["latest_ohr"]=ratings[0]
    return d

def parse(raw):
    warnings=[];header=parse_header(raw);runners=parse_summary(raw)
    if not runners:return header,[],["Could not locate the harness runners table."]
    blocks=_blocks(raw,runners)
    for r in runners:
        if r["tab"] in blocks:r.update(_parse_block(blocks[r["tab"]],r))
        else:warnings.append(f"No detail block found for #{r['tab']} {r['horse']}.")
        for k,v in [("form",""),("bf_odds",r.get("tab_odds",999.0)),("driver_win",.10),("driver_place",.32),("trainer_win",.10),("trainer_place",.32),("driver_horse_win",0.0),("driver_horse_place",0.0),("driver_horse_n",0),("driver_trainer_win",0.0),("driver_trainer_place",0.0),("driver_trainer_n",0),("dls",14),("recent_runs",[])]:r.setdefault(k,v)
        for key in ("career","12m","course","distance","course_distance"):
            r.setdefault(f"{key}_rec","0-0-0");r.setdefault(f"{key}_wins",0);r.setdefault(f"{key}_places",0);r.setdefault(f"{key}_starts",0)
    return header,runners,warnings
