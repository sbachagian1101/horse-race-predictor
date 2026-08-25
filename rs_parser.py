"""Racing & Sports thoroughbred Enhanced Form parser.

Designed to tolerate:
- Markdown-ish copies (e.g. ChatGPT / browser save)
- direct browser clipboard text with tabs
- direct browser clipboard text flattened into one value per line

If the summary table cannot be reconstructed, active runners are recovered from
stable detail-block anchors ("HORSE ...yo ... (BP: n) xx.xkg") so parsing never
depends on one exact clipboard layout.
"""
from __future__ import annotations
import re
from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).replace("$", "").replace(",", "").replace("%", "").strip())
    except Exception:
        return default


def _name(v: str) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().upper()


def _clean(text: str) -> str:
    text = (
        str(text or "")
        .replace("\xa0", " ")
        .replace("\u2003", " ")
        .replace("\u2002", " ")
        .replace("\u202f", " ")
    )
    text = text.replace("\\-", "-").replace("\\:", ":").replace("\\&", "&")
    text = re.sub(r"\[([^\]]+)\]\([^\n]*?\)", r"\1", text)
    text = text.replace("***", "").replace("**", "").replace("__", "")
    text = re.sub(r"^[#>*]+\s*", "", text, flags=re.M)
    text = re.sub(r"^[ \t]*[-*][ \t]+(?=[A-Za-z\[])", "", text, flags=re.M)
    return "\n".join(x.strip() for x in text.splitlines())


def _link(c: str) -> str:
    m = re.search(r"\[\**([^\]]+?)\**\]\(", c)
    return (m.group(1) if m else re.sub(r"[\[\]*]", "", c)).strip()


def _after(block: str, label: str) -> str:
    """Return the value following a label, whether it is same-line or next-line."""
    ls = [x.strip() for x in block.splitlines()]
    target = label.lower().strip()
    for i, x in enumerate(ls):
        xl = x.lower().strip()
        if xl == target:
            for y in ls[i + 1 : i + 5]:
                if y:
                    return y.strip()
        elif xl.startswith(target):
            tail = x[len(label) :].strip(" \t:|-")
            if tail:
                return tail
    m = re.search(
        rf"(?is)(?<!\w){re.escape(label)}(?!\w)\s*[:|]?\s*([^\n|]+)",
        block,
    )
    return m.group(1).strip() if m else ""


def _record(v: str):
    s = re.sub(r"\s+", "", v or "")
    m = re.fullmatch(r"(\d+)-(\d+)-(\d+)", s)
    if m:
        w, p, n = map(int, m.groups())
        return s, w, p, n, w / max(n, 1), (w + p) / max(n, 1)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)%-(\d+(?:\.\d+)?)%-(\d+)", s)
    if m:
        wp, tp, n = float(m.group(1)), float(m.group(2)), int(m.group(3))
        w = round(n * wp / 100)
        top = round(n * tp / 100)
        return s, int(w), max(int(top - w), 0), n, wp / 100, tp / 100
    return "0-0-0", 0, 0, 0, 0.0, 0.0


def _form_price(text: str):
    ms = list(
        re.finditer(
            r"(?i)(?<![A-Za-z0-9])([0-9xXfF]{1,10})\s+\$([0-9]+(?:\.[0-9]+)?)",
            text,
        )
    )
    return ms[-1] if ms else None


def parse_race_header(raw: str) -> dict[str, Any]:
    t = _clean(raw)
    h: dict[str, Any] = {}
    m = re.search(r"(?mi)^(.+?)\s+Form Guide\s*\(Race\s*(\d+)\)", t)
    if m:
        h["track"], h["race_no"] = m.group(1).strip(), int(m.group(2))
    m = re.search(
        r"(?mi)^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(.+?\d{4})$",
        t,
    )
    if m:
        h["date"] = f"{m.group(1)}, {m.group(2)}"
    m = re.search(r"(?m)^(\d{1,2}:\d{2})\s*$", t)
    if m:
        h["time"] = m.group(1)
    m = re.search(r"(?is)\(local\)\s*\n+\s*([^\n]+)", t)
    if m:
        candidate = m.group(1).strip()
        if candidate and not re.match(r"^(Age|Sex|WT|Type|Fastest Time)\s*:", candidate, re.I):
            h["race_name"] = candidate
    m = re.search(r"(?i)Type:\s*([A-Za-z0-9+\-/]+)", t)
    if m:
        h["race_class"] = m.group(1).strip()
    m = re.search(r"AUD\s*\$([\d,]+)", t, re.I)
    if m:
        h["prize"] = f"AUD ${m.group(1)}"
    m = re.search(
        r"(?mi)^(\d{3,4})m\s+(ALL WEATHER|SYNTHETIC|TURF|AW|SAND|DIRT|POLY)\s+([^\n]+?)\s*$",
        t,
    )
    if m:
        h["distance_m"] = int(m.group(1))
        h["surface"] = m.group(2).upper()
        h["going"] = m.group(3).upper()
    return h


def _summary_markdown(raw: str) -> list[dict[str, Any]]:
    out = []
    for line in raw.splitlines():
        if not re.match(r"^\|\s*\d{1,2}\s*\|", line.strip()):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 8:
            continue
        wt = re.sub(r"[* ]", "", c[2])
        if not re.fullmatch(r"\d{2,3}(?:\.\d+)?", wt):
            continue
        tab_s = re.sub(r"\D", "", c[0])
        if not tab_s:
            continue
        tab = int(tab_s)
        jr = _link(c[4])
        cm = re.search(r"\(a(\d+(?:\.\d+)?)\)", jr, re.I)
        scr = any(re.search(r"\bscr\b", x, re.I) for x in c[8:])
        odds = 999.0
        for x in reversed(c[8:]):
            z = re.sub(r"[*$]", "", x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", z):
                odds = _f(z, 999)
                break
        out.append(
            {
                "tab": tab,
                "horse": _name(_link(c[1])),
                "wt": _f(c[2]),
                "bp": int(_f(c[3], 0)),
                "jockey": _name(re.sub(r"\s*\(a\d+(?:\.\d+)?\)", "", jr, flags=re.I)),
                "claim": _f(cm.group(1)) if cm else 0,
                "jrat": _f(re.sub(r"^\**H\**\s*", "", c[5], flags=re.I)),
                "trainer": _name(_link(c[6])),
                "trat": _f(re.sub(r"^\**H\**\s*", "", c[7], flags=re.I)),
                "tab_odds": 999.0 if scr else odds,
                "scratched": scr,
            }
        )
    return out


def _field_segment(raw: str) -> str:
    t = _clean(raw)
    start = re.search(r"(?mi)^.*TabHorseWTBPJockeyJRatTrainerTRat.*$", t)
    if not start:
        start = re.search(r"(?mi)^Tab\s*Horse\s*WT\s*BP\s*Jockey.*Trainer.*$", t)
    end = re.search(r"(?mi)^Explanations\s*$", t)
    if not start:
        return ""
    return t[start.end() : end.start() if end and end.start() > start.end() else len(t)]


def _summary_plain(raw: str) -> list[dict[str, Any]]:
    """Parse direct browser clipboard text when the HTML table is flattened."""
    seg = _field_segment(raw)
    if not seg:
        return []
    out = []
    for line in seg.splitlines():
        if "\t" not in line:
            continue
        p = [x.strip() for x in line.split("\t") if x.strip()]
        if len(p) < 8 or not re.fullmatch(r"\d{1,2}", p[0]):
            continue
        if not re.fullmatch(r"\d{2,3}(?:\.\d+)?", p[2]):
            continue
        tab = int(p[0])
        jr = p[4]
        cm = re.search(r"\(a(\d+(?:\.\d+)?)\)", jr, re.I)
        scr = any(re.search(r"\bscr\b", x, re.I) for x in p)
        nums_after = []
        for x in p[8:]:
            z = re.sub(r"[$*]", "", x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", z):
                nums_after.append(_f(z))
        out.append(
            {
                "tab": tab,
                "horse": _name(p[1]),
                "wt": _f(p[2]),
                "bp": int(_f(p[3], 0)),
                "jockey": _name(re.sub(r"\s*\(a\d+(?:\.\d+)?\)", "", jr, flags=re.I)),
                "claim": _f(cm.group(1)) if cm else 0,
                "jrat": _f(re.sub(r"^H\s*", "", p[5], flags=re.I)),
                "trainer": _name(p[6]),
                "trat": _f(re.sub(r"^H\s*", "", p[7], flags=re.I)),
                "tab_odds": 999.0 if scr else (nums_after[-1] if nums_after else 999.0),
                "scratched": scr,
            }
        )
    if out:
        return out
    lines = [
        x.strip()
        for x in seg.splitlines()
        if x.strip()
        and not (len(x.strip()) > 3 and re.match(r"^\|?[- :]+\|?$", x.strip()))
        and "TabHorseWTBPJockeyJRatTrainerTRat" not in x
    ]
    starts = [
        i for i in range(len(lines) - 2)
        if re.fullmatch(r"\d{1,2}", lines[i])
        and re.search(r"[A-Za-z]", lines[i + 1])
        and re.fullmatch(r"\d{2,3}(?:\.\d+)?", lines[i + 2])
        and 40 <= _f(lines[i + 2]) <= 80
    ]
    for si, i in enumerate(starts):
        j = starts[si + 1] if si + 1 < len(starts) else len(lines)
        chunk = lines[i:j]
        if len(chunk) < 7:
            continue
        tab = int(chunk[0])
        horse = _name(chunk[1])
        wi = next(
            (
                k for k in range(2, len(chunk))
                if re.fullmatch(r"\d{2,3}(?:\.\d+)?", chunk[k])
                and 40 <= _f(chunk[k]) <= 80
            ),
            None,
        )
        if wi is None or wi + 4 >= len(chunk):
            continue
        wt = _f(chunk[wi])
        bp = int(_f(chunk[wi + 1], 0))
        jockey_raw = chunk[wi + 2]
        cm = re.search(r"\(a(\d+(?:\.\d+)?)\)", jockey_raw, re.I)
        jrat = _f(re.sub(r"^H\s*", "", chunk[wi + 3], flags=re.I))
        trainer = chunk[wi + 4]
        trat = _f(re.sub(r"^H\s*", "", chunk[wi + 5], flags=re.I)) if wi + 5 < len(chunk) else 0
        scr = any(re.search(r"\bscr\b", x, re.I) for x in chunk)
        odds = 999.0
        for x in reversed(chunk[wi + 6 :]):
            z = re.sub(r"[$*]", "", x).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", z):
                odds = _f(z, 999)
                break
        out.append(
            {
                "tab": tab,
                "horse": horse,
                "wt": wt,
                "bp": bp,
                "jockey": _name(re.sub(r"\s*\(a\d+(?:\.\d+)?\)", "", jockey_raw, flags=re.I)),
                "claim": _f(cm.group(1)) if cm else 0,
                "jrat": jrat,
                "trainer": _name(trainer),
                "trat": trat,
                "tab_odds": 999.0 if scr else odds,
                "scratched": scr,
            }
        )
    return out


def _detail_anchors(raw: str):
    t = _clean(raw)
    pat = re.compile(
        r"(?mi)^([A-Z][A-Z0-9'’ .&\-]+?)\s+(\d+)yo\s+([A-Z/]+)\s+([A-Za-z]+)\b"
        r"[^\n]*?\(BP:\s*([0-9]+|-)\)\s*([\d.]+)kg\s*$"
    )
    return t, list(pat.finditer(t))


def _summary_from_details(raw: str) -> list[dict[str, Any]]:
    t, anchors = _detail_anchors(raw)
    if not anchors:
        return []
    field = _field_segment(raw)
    out = []
    used_tabs = set()
    for idx, m in enumerate(anchors):
        horse = _name(m.group(1))
        pos = m.start()
        prefix_start = max(0, pos - 500)
        prefix = t[prefix_start:pos]
        pair = _form_price(prefix)
        form = pair.group(1) if pair else ""
        bf = _f(pair.group(2), 999.0) if pair else 999.0
        tab = 0
        if pair:
            before_pair = prefix[: pair.start()]
            nums = re.findall(r"(?m)^\s*(\d{1,2})\s*$", before_pair)
            for z in reversed(nums):
                cand = int(z)
                if 1 <= cand <= 30 and cand not in used_tabs:
                    tab = cand
                    break
        if not tab:
            tab = idx + 1
            while tab in used_tabs:
                tab += 1
        used_tabs.add(tab)
        scr = False
        if field:
            nm = re.search(re.escape(horse), field, re.I)
            if nm:
                following = field[nm.end() : nm.end() + 350]
                scr = bool(re.search(r"\bScr\b", following, re.I))
        out.append(
            {
                "tab": tab,
                "horse": horse,
                "wt": _f(m.group(6)),
                "bp": int(_f(m.group(5), 0)),
                "jockey": "",
                "claim": 0.0,
                "jrat": 0.0,
                "trainer": "",
                "trat": 0.0,
                "tab_odds": 999.0 if scr else bf,
                "scratched": scr,
                "_detail_form_hint": form.lower(),
                "_detail_bf_hint": bf,
            }
        )
    return out


def parse_summary_table(raw: str) -> list[dict[str, Any]]:
    rows = _summary_markdown(raw)
    if not rows:
        rows = _summary_plain(raw)
    if not rows:
        rows = _summary_from_details(raw)
    seen = set()
    clean = []
    for r in rows:
        if r["tab"] not in seen and r.get("horse"):
            clean.append(r)
            seen.add(r["tab"])
    return clean


def _blocks(raw: str, runners: list[dict[str, Any]]) -> dict[int, str]:
    t = _clean(raw)
    starts = []
    for r in runners:
        m = re.search(rf"(?mi)^\s*{re.escape(r['horse'])}\s+(\d+)yo\b[^\n]*$", t)
        if m:
            starts.append((m.start(), r["tab"]))
    starts.sort()
    out = {}
    for i, (pos, tab) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(t)
        ps = max(0, pos - 500)
        pref = t[ps:pos]
        pair = _form_price(pref)
        st = ps + (pair.start() if pair else 0)
        out[tab] = t[st:end]
    return out


def _recent(block: str):
    ls = [x.strip() for x in block.splitlines()]
    out = []
    for i, line in enumerate(ls):
        if "Margin" not in line or "Distance" not in line or "Race Time" not in line or "Trial Time" in line:
            continue
        r = {}
        floor = max(0, i - 32)
        for j in range(floor, i):
            m = re.fullmatch(r"(\d+)\s+of\s+(\d+)", ls[j], re.I)
            if m:
                r["finish"], r["field"] = int(m.group(1)), int(m.group(2))
            if ls[j].upper() == "OHR":
                k = j - 1
                while k >= floor and not ls[k]:
                    k -= 1
                if k >= floor and re.fullmatch(r"\d{1,3}", ls[k]):
                    r["ohr"] = int(ls[k])
        for key, pat, typ in [
            ("margin", r"\bMargin\s*([\d.]+)L", float),
            ("distance", r"\bDistance\s*(\d+)m", int),
            ("sp", r"\bSP\s*\$([\d.]+)", float),
            ("weight", r"\bWeight\s*([\d.]+)", float),
            ("prior_box", r"\bBP\s*(\d+)", int),
            ("sec_time", r"\bSec Time\s*([\d.]+)", float),
        ]:
            m = re.search(pat, line, re.I)
            if m:
                r[key] = typ(m.group(1))
        m = re.search(r"\bClass\s*(.*?)\s*Prize\b", line, re.I)
        if m:
            r["class"] = m.group(1).strip()
        m = re.search(r"\bGear Change\s*(.*?)(?=\s*Stewards|\s*Inrunning Position|\s*Tempo|\s*Race/Horse Sectionals:|\s*Video Comments|$)", line, re.I)
        if m:
            r["gear_change"] = m.group(1).strip()
        m = re.search(r"\bStewards\s*(.*?)(?=\s*Inrunning Position|\s*Tempo|\s*Race/Horse Sectionals:|\s*Video Comments|$)", line, re.I)
        if m:
            r["stewards"] = m.group(1).strip()
        m = re.search(r"Inrunning Position\s*(\d+)(?:st|nd|rd|th) Place on settling", line, re.I)
        if m:
            r["settle_pos"] = int(m.group(1))
        m = re.search(r"(\d+)(?:st|nd|rd|th) Place at 800m", line, re.I)
        if m:
            r["pos800"] = int(m.group(1))
        m = re.search(r"(\d+)(?:st|nd|rd|th) Place on turn", line, re.I)
        if m:
            r["turn_pos"] = int(m.group(1))
        out.append(r)
    return out


def _parse_block(block: str, runner: dict[str, Any]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    pair = _form_price(block[:600])
    if pair:
        d["form5"], d["bf_odds"] = pair.group(1).lower(), _f(pair.group(2), 999)
    elif runner.get("_detail_form_hint"):
        d["form5"] = runner["_detail_form_hint"]
        d["bf_odds"] = runner.get("_detail_bf_hint", 999.0)
    m = re.search(rf"(?mi)^\s*{re.escape(runner['horse'])}\s+(\d+)yo\s+([A-Z/]+)\s+([A-Za-z]+)\b", block)
    if m:
        d["age"], d["colour"], d["sex"] = int(m.group(1)), m.group(2), m.group(3)
    sire = _after(block, "Sire")
    if sire:
        d["sire"] = sire
    jockey = _after(block, "Jockey")
    if jockey:
        d["jockey"] = _name(re.sub(r"\s*\(a\d+(?:\.\d+)?\)", "", jockey, flags=re.I))
    trainer = _after(block, "Trainer")
    if trainer:
        d["trainer"] = _name(trainer)
    l50 = re.findall(r"(?is)(?<!\w)Last50(?!\w)\s*[:|]?\s*(\d+)%-(\d+)%-(\d+)", block)
    if l50:
        d["jky_win"], d["jky_place"] = int(l50[0][0]) / 100, int(l50[0][1]) / 100
    if len(l50) > 1:
        d["trn_win"], d["trn_place"] = int(l50[1][0]) / 100, int(l50[1][1]) / 100
    jt = _record(_after(block, "J/T"))
    d["jt_win"] = jt[4]
    mapping = {
        "Car": "Car", "12m": "12m", "Crs": "Crs", "Dist": "Dist",
        "Crs & Dist": "CrsDist", "Good": "Good", "Soft": "Soft",
        "Heavy": "Heavy", "AW": "AW", "Turf": "Turf",
    }
    for lab, key in mapping.items():
        disp, w, p, n, wr, pr = _record(_after(block, lab))
        d[f"{key}_rec"] = disp
        d[f"{key}_win"] = wr
        d[f"{key}_plc"] = pr
        d[f"{key}_starts"] = n
    x = _after(block, "DLS")
    mm = re.search(r"\d+", x)
    if mm:
        d["dslr"] = int(mm.group())
    m = re.search(r"Days Since Last Run:\s*(\d+)\s*days(?:\s*\((\d+)U\))?", block, re.I)
    if m:
        d["dslr"] = int(m.group(1))
        if m.group(2):
            d["runs_this_prep"] = int(m.group(2))
    x = _after(block, "RTC/km")
    if "runs_this_prep" not in d and re.match(r"\d+", x):
        d["runs_this_prep"] = int(re.match(r"\d+", x).group())
    x = _after(block, "Car PM")
    m = re.search(r"\$([\d,.]+)\s*([kKmM]?)", x)
    if m:
        val = float(m.group(1).replace(",", "")); unit = m.group(2).lower()
        d["career_pm_k"] = val * 1000 if unit == "m" else val if unit == "k" else val / 1000
    x = _after(block, "12m PM")
    m = re.search(r"\$([\d,.]+)\s*([kKmM]?)", x)
    if m:
        val = float(m.group(1).replace(",", "")); unit = m.group(2).lower()
        d["pm_12m"] = val * 1e6 if unit == "m" else val * 1000 if unit == "k" else val
    d["recent_runs"] = _recent(block)
    if d["recent_runs"]:
        last = d["recent_runs"][0]
        for a, b in [("finish", "last_fin"), ("ohr", "ohr"), ("margin", "ls_margin"), ("distance", "ls_dist"), ("class", "ls_class"), ("sp", "ls_sp")]:
            if a in last:
                d[b] = last[a]
        d["gear_change"] = bool(last.get("gear_change"))
    ratings = [x["ohr"] for x in d["recent_runs"] if x.get("ohr")]
    if "ohr" not in d and ratings:
        d["ohr"] = ratings[0]
    if "last_fin" not in d and d.get("form5"):
        z = re.sub(r"\D", "", d["form5"])
        if z:
            d["last_fin"] = 10 if z[-1] == "0" else int(z[-1])
    d.setdefault("gear_change", False)
    d["had_trial"] = bool(re.search(r"(?mi)^BT\s*$|BT Results", block))
    return d


def parse(raw: str):
    warnings: list[str] = []
    header = parse_race_header(raw)
    runners = parse_summary_table(raw)
    if not runners:
        return header, [], ["Could not locate runners in either the field table or the detailed runner blocks."]
    blocks = _blocks(raw, runners)
    for r in runners:
        if r["tab"] in blocks:
            r.update(_parse_block(blocks[r["tab"]], r))
        else:
            warnings.append(f"No detail block found for #{r['tab']} {r['horse']}.")
        if r.get("tab_odds", 999.0) >= 999 and r.get("bf_odds", 999.0) < 999 and not r.get("scratched"):
            r["tab_odds"] = r["bf_odds"]
        r.setdefault("bf_odds", r.get("tab_odds", 999.0))
        r.setdefault("ohr", 0)
        r.setdefault("dslr", 30)
        r.setdefault("runs_this_prep", 1)
        r.setdefault("last_fin", 10)
        r.setdefault("jky_win", 0.05)
        r.setdefault("trn_win", 0.05)
        r.setdefault("jt_win", 0.0)
        for key in ("Car", "12m", "Crs", "Dist", "CrsDist", "Good", "Soft", "Heavy"):
            r.setdefault(f"{key}_rec", "0-0-0")
            r.setdefault(f"{key}_win", 0.0)
            r.setdefault(f"{key}_plc", 0.0)
            r.setdefault(f"{key}_starts", 0)
        for k, v in [("form5", ""), ("career_pm_k", 0.0), ("pm_12m", 0.0), ("ls_margin", 0.0), ("ls_dist", 0), ("ls_class", ""), ("ls_sp", 0.0), ("gear_change", False), ("had_trial", False)]:
            r.setdefault(k, v)
        r.pop("_detail_form_hint", None)
        r.pop("_detail_bf_hint", None)
    active = [r for r in runners if not r.get("scratched")]
    if any(r["tab"] not in blocks for r in active):
        warnings.append("Detailed form was not parsed for one or more active runners.")
    if not _summary_markdown(raw) and not _summary_plain(raw):
        warnings.append("The browser clipboard flattened the field table; runners were recovered from detail blocks and Betfair prices were used as the market fallback.")
    return header, runners, warnings
