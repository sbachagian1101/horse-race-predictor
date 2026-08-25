"""Racing & Sports thoroughbred Enhanced Form parser."""
from __future__ import annotations
import re
from typing import Any

def _f(v: Any, default: float=0.0)->float:
    try:return float(str(v).replace("$","").replace(",","").replace("%","").strip())
    except:return default
def _name(v:str)->str:return re.sub(r"\s+"," ",str(v or "")).strip().upper()
def _clean(text:str)->str:
    text=str(text or "").replace("\xa0"," ").replace("\u2003"," ").replace("\u2002"," ").replace("\u202f"," ")
    text=text.replace("\\-","-").replace("\\:",":").replace("\\&","&")
    text=re.sub(r"\[([^\]]+)\]\([^\n]*?\)",r"\1",text)
    text=text.replace("***","").replace("**","").replace("__","")
    text=re.sub(r"^[#>*]+\s*","",text,flags=re.M)
    text=re.sub(r"^\s*[-*]\s+(?=[A-Za-z\[])","",text,flags=re.M)
    return "\n".join(x.strip() for x in text.splitlines())
def _link(c:str)->str:
    m=re.search(r"\[\**([^\]]+?)\**\]\(",c)
    return (m.group(1) if m else re.sub(r"[\[\]*]","",c)).strip()
def _after(block:str,label:str)->str:
    ls=[x.strip() for x in block.splitlines()]
    for i,x in enumerate(ls[:-1]):
        if x.lower()==label.lower():
            for y in ls[i+1:i+5]:
                if y:return y
    return ""
def _record(v:str):
    s=re.sub(r"\s+","",v or "")
    m=re.fullmatch(r"(\d+)-(\d+)-(\d+)",s)
    if m:
        w,p,n=map(int,m.groups()); return s,w,p,n,w/max(n,1),(w+p)/max(n,1)
    m=re.fullmatch(r"(\d+(?:\.\d+)?)%-(\d+(?:\.\d+)?)%-(\d+)",s)
    if m:
        wp,tp,n=float(m.group(1)),float(m.group(2)),int(m.group(3)); w=round(n*wp/100); top=round(n*tp/100)
        return s,int(w),max(int(top-w),0),n,wp/100,tp/100
    return "0-0-0",0,0,0,0.0,0.0

def parse_race_header(raw:str)->dict[str,Any]:
    t=_clean(raw); h={}
    m=re.search(r"(?mi)^(.+?)\s+Form Guide\s*\(Race\s*(\d+)\)",t)
    if m:h["track"],h["race_no"]=m.group(1).strip(),int(m.group(2))
    m=re.search(r"(?mi)^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(.+?\d{4})$",t)
    if m:h["date"]=f"{m.group(1)}, {m.group(2)}"
    m=re.search(r"(?is)\(local\)\s*\n+\s*([^\n]+?)\s*\n+\s*WT:",t)
    if m:h["race_name"]=m.group(1).strip()
    m=re.search(r"(?i)Type:\s*([^\s\n]+)",t)
    if m:h["race_class"]=m.group(1).strip()
    m=re.search(r"AUD\s*\$([\d,]+)",t,re.I)
    if m:h["prize"]=f"AUD ${m.group(1)}"
    m=re.search(r"(?mi)^(\d{3,4})m\s+(TURF|AW|SAND|DIRT|POLY)\s+([A-Z]+(?:\s+\d+)?)\s*$",t)
    if m:h["distance_m"],h["surface"],h["going"]=int(m.group(1)),m.group(2).upper(),m.group(3).upper()
    return h

def parse_summary_table(raw:str)->list[dict[str,Any]]:
    out=[]
    for line in raw.splitlines():
        if not re.match(r"^\|\s*\d{1,2}\s*\|",line.strip()):continue
        c=[x.strip() for x in line.strip().strip("|").split("|")]
        if len(c)<8 or not re.fullmatch(r"\d{2,3}(?:\.\d+)?",re.sub(r"[* ]","",c[2])):continue
        tab=int(re.sub(r"\D","",c[0])); jr=_link(c[4]); cm=re.search(r"\(a(\d+(?:\.\d+)?)\)",jr,re.I)
        scr=any(re.search(r"\bscr\b",x,re.I) for x in c[8:]); odds=999.0
        for x in reversed(c[8:]):
            z=re.sub(r"[*$]","",x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?",z):odds=_f(z,999);break
        out.append({"tab":tab,"horse":_name(_link(c[1])),"wt":_f(c[2]),"bp":int(_f(c[3],0)),
          "jockey":_name(re.sub(r"\s*\(a\d+(?:\.\d+)?\)","",jr,flags=re.I)),"claim":_f(cm.group(1)) if cm else 0,
          "jrat":_f(re.sub(r"^\**H\**\s*","",c[5],flags=re.I)),"trainer":_name(_link(c[6])),
          "trat":_f(re.sub(r"^\**H\**\s*","",c[7],flags=re.I)),"tab_odds":999.0 if scr else odds,"scratched":scr})
    seen=set(); clean=[]
    for r in out:
        if r["tab"] not in seen:clean.append(r);seen.add(r["tab"])
    return clean

def _blocks(raw,runners):
    t=_clean(raw); starts=[]
    for r in runners:
        m=re.search(rf"(?mi)^\s*{re.escape(r['horse'])}\s+(\d+)yo\b[^\n]*$",t)
        if m:starts.append((m.start(),r["tab"]))
    starts.sort(); out={}
    for i,(pos,tab) in enumerate(starts):
        end=starts[i+1][0] if i+1<len(starts) else len(t); ps=max(0,pos-320); pref=t[ps:pos]
        pairs=list(re.finditer(r"(?mi)^\s*([0-9xXfF]{1,10})\s*$\s*^\s*\$([0-9]+(?:\.\d+)?)\s*$",pref))
        st=ps+(pairs[-1].start() if pairs else 0); out[tab]=t[st:end]
    return out

def _recent(block):
    ls=[x.strip() for x in block.splitlines()]; out=[]
    for i,line in enumerate(ls):
        if "Margin" not in line or "Distance" not in line or "Race Time" not in line or "Trial Time" in line:continue
        r={}; floor=max(0,i-30)
        for j in range(floor,i):
            m=re.fullmatch(r"(\d+)\s+of\s+(\d+)",ls[j],re.I)
            if m:r["finish"],r["field"]=int(m.group(1)),int(m.group(2))
            if ls[j].upper()=="OHR":
                k=j-1
                while k>=floor and not ls[k]:k-=1
                if k>=floor and re.fullmatch(r"\d{1,3}",ls[k]):r["ohr"]=int(ls[k])
        for key,pat,typ in [("margin",r"\bMargin\s*([\d.]+)L",float),("distance",r"\bDistance\s*(\d+)m",int),("sp",r"\bSP\s*\$([\d.]+)",float),("weight",r"\bWeight\s*([\d.]+)",float),("prior_box",r"\bBP\s*(\d+)",int),("sec_time",r"\bSec Time\s*([\d.]+)",float)]:
            m=re.search(pat,line,re.I)
            if m:r[key]=typ(m.group(1))
        m=re.search(r"\bClass\s*(.*?)\s*Prize\b",line,re.I)
        if m:r["class"]=m.group(1).strip()
        m=re.search(r"\bGear Change\s*(.*?)(?=\s*Stewards|\s*Inrunning Position|\s*Tempo|\s*Race/Horse Sectionals:|\s*Video Comments|$)",line,re.I)
        if m:r["gear_change"]=m.group(1).strip()
        m=re.search(r"\bStewards\s*(.*?)(?=\s*Inrunning Position|\s*Tempo|\s*Race/Horse Sectionals:|\s*Video Comments|$)",line,re.I)
        if m:r["stewards"]=m.group(1).strip()
        out.append(r)
    return out

def _parse_block(block,runner):
    d={}
    m=re.search(r"(?mi)^\s*([0-9xXfF]{1,10})\s*$\s*^\s*\$([0-9]+(?:\.\d+)?)\s*$",block[:450])
    if m:d["form5"],d["bf_odds"]=m.group(1).lower(),_f(m.group(2),999)
    m=re.search(rf"(?mi)^\s*{re.escape(runner['horse'])}\s+(\d+)yo\s+([A-Z/]+)\s+([A-Za-z]+)\b",block)
    if m:d["age"],d["colour"],d["sex"]=int(m.group(1)),m.group(2),m.group(3)
    sire=_after(block,"Sire")
    if sire:d["sire"]=sire
    l50=re.findall(r"(?mi)^Last50\s*$\s*^(\d+)%-(\d+)%-(\d+)\s*$",block)
    if l50:d["jky_win"],d["jky_place"]=int(l50[0][0])/100,int(l50[0][1])/100
    if len(l50)>1:d["trn_win"],d["trn_place"]=int(l50[1][0])/100,int(l50[1][1])/100
    jt=_record(_after(block,"J/T")); d["jt_win"]=jt[4]
    mapping={"Car":"Car","12m":"12m","Crs":"Crs","Dist":"Dist","Crs & Dist":"CrsDist","Good":"Good","Soft":"Soft","Heavy":"Heavy"}
    for lab,key in mapping.items():
        disp,w,p,n,wr,pr=_record(_after(block,lab)); d[f"{key}_rec"]=disp;d[f"{key}_win"]=wr;d[f"{key}_plc"]=pr;d[f"{key}_starts"]=n
    x=_after(block,"DLS"); mm=re.search(r"\d+",x)
    if mm:d["dslr"]=int(mm.group())
    m=re.search(r"Days Since Last Run:\s*(\d+)\s*days(?:\s*\((\d+)U\))?",block,re.I)
    if m:
        d["dslr"]=int(m.group(1))
        if m.group(2):d["runs_this_prep"]=int(m.group(2))
    x=_after(block,"RTC/km")
    if "runs_this_prep" not in d and re.match(r"\d+",x):d["runs_this_prep"]=int(re.match(r"\d+",x).group())
    x=_after(block,"Car PM"); m=re.search(r"\$([\d,.]+)\s*([kKmM]?)",x)
    if m:
        val=float(m.group(1).replace(",","")); unit=m.group(2).lower(); d["career_pm_k"]=val*1000 if unit=="m" else val if unit=="k" else val/1000
    x=_after(block,"12m PM"); m=re.search(r"\$([\d,.]+)\s*([kKmM]?)",x)
    if m:
        val=float(m.group(1).replace(",","")); unit=m.group(2).lower(); d["pm_12m"]=val*1e6 if unit=="m" else val*1000 if unit=="k" else val
    d["recent_runs"]=_recent(block)
    if d["recent_runs"]:
        last=d["recent_runs"][0]
        for a,b in [("finish","last_fin"),("ohr","ohr"),("margin","ls_margin"),("distance","ls_dist"),("class","ls_class"),("sp","ls_sp")]:
            if a in last:d[b]=last[a]
        d["gear_change"]=bool(last.get("gear_change"))
    ratings=[x["ohr"] for x in d["recent_runs"] if x.get("ohr")]
    if "ohr" not in d and ratings:d["ohr"]=ratings[0]
    if "last_fin" not in d and d.get("form5"):
        z=re.sub(r"\D","",d["form5"])
        if z:d["last_fin"]=10 if z[-1]=="0" else int(z[-1])
    d.setdefault("gear_change",False); d["had_trial"]=bool(re.search(r"(?mi)^BT\s*$|BT Results",block)); return d

def parse(raw:str):
    warnings=[];header=parse_race_header(raw);runners=parse_summary_table(raw)
    if not runners:return header,[],["Could not locate runners summary table."]
    blocks=_blocks(raw,runners)
    for r in runners:
        if r["tab"] in blocks:r.update(_parse_block(blocks[r["tab"]],r))
        else:warnings.append(f"No detail block found for #{r['tab']} {r['horse']}.")
        r.setdefault("bf_odds",r.get("tab_odds",999.0));r.setdefault("ohr",0);r.setdefault("dslr",30);r.setdefault("runs_this_prep",1);r.setdefault("last_fin",10);r.setdefault("jky_win",.05);r.setdefault("trn_win",.05);r.setdefault("jt_win",0.0)
        for key in ("Car","12m","Crs","Dist","CrsDist","Good","Soft","Heavy"):
            r.setdefault(f"{key}_rec","0-0-0");r.setdefault(f"{key}_win",0.0);r.setdefault(f"{key}_plc",0.0);r.setdefault(f"{key}_starts",0)
        for k,v in [("form5",""),("career_pm_k",0.0),("pm_12m",0.0),("ls_margin",0.0),("ls_dist",0),("ls_class",""),("ls_sp",0.0),("gear_change",False),("had_trial",False)]:r.setdefault(k,v)
    active=[r for r in runners if not r.get("scratched")]
    if any(r["tab"] not in blocks for r in active):warnings.append("Detailed form was not parsed for one or more active runners.")
    return header,runners,warnings
