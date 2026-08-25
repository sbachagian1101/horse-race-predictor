"""Racing & Sports harness Enhanced Form paste parser.

Designed for the Markdown-ish text produced by copied Racing & Sports harness
Enhanced Form pages. The field table supplies runners, driver/trainer names,
prices and scratches. Detail blocks add driver/trainer strike rates, course and
distance records, ratings, adjusted mile rates, sectionals, barriers/HCP from
recent starts, in-running positions and steward comments.
"""
from __future__ import annotations

import re
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        s = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
        mult = 1.0
        if s.lower().endswith("k"):
            mult, s = 1000.0, s[:-1]
        elif s.lower().endswith("m"):
            mult, s = 1_000_000.0, s[:-1]
        return float(s) * mult
    except Exception:
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _time_seconds(value: str | float | int | None, default: float = 0.0) -> float:
    if value is None:
        return default
    s = str(value).strip()
    try:
        if ":" not in s:
            return float(s)
        parts = s.split(":")
        if len(parts) == 2:
            return 60.0 * float(parts[0]) + float(parts[1])
        if len(parts) == 3:
            return 3600.0 * float(parts[0]) + 60.0 * float(parts[1]) + float(parts[2])
    except Exception:
        pass
    return default


def _triple(value: str) -> tuple[int, int, int]:
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", value or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _clean_md(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u2003", " ").replace("\u2002", " ")
    text = text.replace("\\-", "-").replace("\\:", ":").replace("\\&", "&")
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = text.replace("***", "").replace("**", "").replace("__", "")
    text = re.sub(r"^[#>*-]+\s*", "", text, flags=re.M)
    return "\n".join(line.strip() for line in text.splitlines())


def parse_header(raw: str) -> dict[str, Any]:
    t = _clean_md(raw)
    h: dict[str, Any] = {}
    m = re.search(r"^(.+?)\s+Form Guide\s*\(Race\s*(\d+)\)", t, re.M | re.I)
    if m:
        h["track"], h["race_no"] = m.group(1).strip(), int(m.group(2))
    m = re.search(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(.+?\d{4})$", t, re.M | re.I)
    if m:
        h["date"] = f"{m.group(1)}, {m.group(2)}"
    m = re.search(r"^(\d{1,2}:\d{2})\s*$", t, re.M)
    if m:
        h["time"] = m.group(1)
    m = re.search(r"\(local\)\s*\n\s*([A-Z0-9][A-Z0-9 '&+()\-/\.]+)\s*\n\s*Fastest Time:", t, re.S)
    if m:
        h["race_name"] = m.group(1).strip()
    m = re.search(r"Fastest Time:\s*([0-9:.]+)", t, re.I)
    if m:
        h["fastest_time"] = m.group(1)
    m = re.search(r"AUD\s*\$([\d,]+)", t)
    if m:
        h["prize"] = f"AUD ${m.group(1)}"
    m = re.search(r"^(\d{3,4})m\s+([A-Z ]+?)\s+(FAST|GOOD|SLOW|WET|HEAVY)\s*$", t, re.M | re.I)
    if m:
        h["distance_m"] = int(m.group(1))
        h["surface"] = m.group(2).strip().upper()
        h["going"] = m.group(3).upper()
    return h


def _link_text(cell: str) -> str:
    m = re.search(r"\[\**([^\]]+?)\**\]\(", cell)
    return (m.group(1) if m else re.sub(r"[\[\]*]", "", cell)).strip()


def _summary_markdown(raw: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not re.match(r"^\|\s*\d{1,2}\s*\|", line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 8:
            continue
        tab = _i(re.sub(r"\D", "", cells[0]))
        if not 1 <= tab <= 20:
            continue
        horse = _link_text(cells[1]).upper()
        if not horse or horse.startswith("HTTP"):
            continue
        driver = _link_text(cells[4]).upper() if len(cells) > 4 else ""
        trainer = _link_text(cells[7]).upper() if len(cells) > 7 else ""
        scratch = any("scr" in c.lower() for c in cells)
        odds = 999.0
        for c in reversed(cells):
            c2 = re.sub(r"[*$]", "", c).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", c2):
                odds = _f(c2, 999.0)
                break
        if scratch:
            odds = 999.0
        out.append({
            "tab": tab,
            "gate": tab,
            "horse": horse,
            "driver": driver,
            "trainer": trainer,
            "total_pm": _f(cells[2]) if len(cells) > 2 else 0.0,
            "pm_per_start": _f(cells[3]) if len(cells) > 3 else 0.0,
            "driver_l50_pm": _f(cells[5]) if len(cells) > 5 else 0.0,
            "driver_total_pm": _f(cells[6]) if len(cells) > 6 else 0.0,
            "trainer_l50_pm": _f(cells[8]) if len(cells) > 8 else 0.0,
            "trainer_total_pm": _f(cells[9]) if len(cells) > 9 else 0.0,
            "scratched": scratch,
            "tab_odds": odds,
        })
    return out


def _summary_plain(raw: str) -> list[dict[str, Any]]:
    t = _clean_md(raw)
    out: list[dict[str, Any]] = []
    for line in t.splitlines():
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) >= 5 and re.fullmatch(r"\d{1,2}", parts[0]) and re.search(r"[A-Za-z]", parts[1]):
            tab = int(parts[0])
            scratch = any("scr" in p.lower() for p in parts)
            odds = 999.0
            for p in reversed(parts):
                if re.fullmatch(r"\d+(?:\.\d+)?", p):
                    odds = _f(p, 999.0); break
            out.append({"tab": tab, "gate": tab, "horse": parts[1].upper(), "driver": parts[4].upper(),
                        "trainer": parts[7].upper() if len(parts)>7 else "", "scratched": scratch,
                        "tab_odds": 999.0 if scratch else odds})
    return out


def parse_summary(raw: str) -> list[dict[str, Any]]:
    runners = _summary_markdown(raw) or _summary_plain(raw)
    seen, dedup = set(), []
    for r in runners:
        if r["tab"] not in seen:
            dedup.append(r); seen.add(r["tab"])
    return dedup


def _runner_blocks(raw: str, runners: list[dict[str, Any]]) -> dict[int, str]:
    t = _clean_md(raw)
    starts: list[tuple[int, int]] = []
    for r in runners:
        pat = re.compile(rf"(?mi)^([0-9xXfF]{{3,8}})\s*\n+\s*{re.escape(r['horse'])}\s+\d+yo\b")
        m = pat.search(t)
        if m:
            starts.append((m.start(), r["tab"]))
    starts.sort()
    blocks: dict[int, str] = {}
    for i, (pos, tab) in enumerate(starts):
        end = starts[i+1][0] if i+1 < len(starts) else len(t)
        blocks[tab] = t[pos:end]
    return blocks


def _extract_label_triple(block: str, label: str) -> str:
    m = re.search(rf"(?mi)^{re.escape(label)}\s*$\s*^\s*(\d+\s*-\s*\d+\s*-\s*\d+)\s*$", block)
    return re.sub(r"\s+", "", m.group(1)) if m else "0-0-0"


def _parse_recent_runs(block: str) -> list[dict[str, Any]]:
    lines = [ln.strip() for ln in block.splitlines()]
    runs: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        if "Margin" not in line or "Distance" not in line or "Race Mile Rate" not in line:
            continue
        r: dict[str, Any] = {}
        for j in range(max(0, i-14), i):
            m = re.fullmatch(r"(\d+)\s+of\s+(\d+)", lines[j], re.I)
            if m:
                r["finish"], r["field"] = int(m.group(1)), int(m.group(2))
            m = re.fullmatch(r"(\d+)(?:st|nd|rd|th)\s+([0-9]+:[0-9.]+)", lines[j], re.I)
            if m:
                r["imr_rank"] = int(m.group(1)); r["imr"] = _time_seconds(m.group(2))
            if lines[j].upper() == "OHR" and j > 0 and re.fullmatch(r"\d{1,3}", lines[j-1]):
                r["ohr"] = int(lines[j-1])
        m = re.search(r"(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", line)
        if m: r["date"] = m.group(1)
        m = re.search(r"([A-Za-z .'-]+)\s*\(AUSTRALIA\):", line, re.I)
        if m: r["track"] = m.group(1).strip().upper()
        specs = {
            "margin": r"Margin\s*([\d.]+)L",
            "distance": r"Distance\s*(\d+)m",
            "race_mile_rate": r"Race Mile Rate\s*([0-9]+:[0-9.]+)",
            "mile_rate_adj": r"Race Mile Rate Adj\s*([+-]?\d+(?:\.\d+)?)",
            "sp": r"\bSP\s*\$([\d.]+)",
        }
        for key, pat in specs.items():
            m = re.search(pat, line, re.I)
            if m:
                if key == "distance": r[key] = int(m.group(1))
                elif key == "race_mile_rate": r[key] = _time_seconds(m.group(1))
                else: r[key] = _f(m.group(1))
        m = re.search(r"\bHCP\s*([A-Za-z]+\d+)", line, re.I)
        if m:
            r["hcp"] = m.group(1).upper()
            gm = re.search(r"(\d+)$", r["hcp"])
            r["prior_gate"] = int(gm.group(1)) if gm else 0
            r["second_row"] = r["hcp"].startswith("SR")
        m = re.search(r"Class\s*(.*?)\s*Prize\b", line, re.I)
        if m: r["class"] = m.group(1).strip()
        m = re.search(r"Stewards\s*(.*?)(?=\s*Inrunning Position|\s*Race/Horse Sectionals:|$)", line, re.I)
        if m: r["stewards"] = m.group(1).strip().rstrip(".")
        for key, pat in (
            ("settle_pos", r"Inrunning Position\s*(\d+)(?:st|nd|rd|th) Place on settling"),
            ("pos1200", r"(\d+)(?:st|nd|rd|th) Place at 1200m"),
            ("pos800", r"(\d+)(?:st|nd|rd|th) Place at 800m"),
            ("bell_pos", r"(\d+)(?:st|nd|rd|th) position at Bell Lap"),
        ):
            m = re.search(pat, line, re.I)
            if m: r[key] = int(m.group(1))
        m = re.search(r"L800m\s*\(R:\s*[\d.]+\)\s*\(H:\s*([\d.]+)", line, re.I)
        if m: r["l800"] = _f(m.group(1))
        else:
            m = re.search(r"L800m\s*\(([\d.]+)\)", line, re.I)
            if m: r["l800"] = _f(m.group(1))
        m = re.search(r"L400m\s*\(R:\s*[\d.]+\)\s*\(H:\s*([\d.]+)", line, re.I)
        if m: r["l400"] = _f(m.group(1))
        else:
            m = re.search(r"L400m\s*\(([\d.]+)\)", line, re.I)
            if m: r["l400"] = _f(m.group(1))
        runs.append(r)
    return runs


def _parse_block(block: str, runner: dict[str, Any]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    m = re.search(r"(?mi)^([0-9xXfF]{3,8})\s*$", block)
    if m: d["form"] = m.group(1).lower()
    m = re.search(rf"(?mi)^{re.escape(runner['horse'])}\s+(\d+)yo\s+([A-Z/]+)\s+([A-Za-z]+)", block)
    if m:
        d["age"], d["colour"], d["sex"] = int(m.group(1)), m.group(2), m.group(3).upper()
    l50s = re.findall(r"(?mi)^Last50\s*$\s*^(\d+)%-(\d+)%-(\d+)\s*$", block)
    if l50s:
        d["driver_win"], d["driver_place"], d["driver_l50_n"] = int(l50s[0][0])/100, int(l50s[0][1])/100, int(l50s[0][2])
    if len(l50s) > 1:
        d["trainer_win"], d["trainer_place"], d["trainer_l50_n"] = int(l50s[1][0])/100, int(l50s[1][1])/100, int(l50s[1][2])
    for label, prefix in (("D/H", "driver_horse"), ("D/T", "driver_trainer")):
        m = re.search(rf"(?mi)^{re.escape(label)}\s*$\s*^(\d+)%-(\d+)%-(\d+)\s*$", block)
        if m:
            d[f"{prefix}_win"], d[f"{prefix}_place"], d[f"{prefix}_n"] = int(m.group(1))/100, int(m.group(2))/100, int(m.group(3))
    m = re.search(r"(?mi)^Raced Dist\.\s*$\s*^(\d+)m\s*-\s*(\d+)m\s*$", block)
    if m: d["raced_dist_min"], d["raced_dist_max"] = int(m.group(1)), int(m.group(2))
    for label, key in (("Car","career"),("12m","12m"),("Crs","course"),("Dist","distance"),("Crs & Dist","course_distance"),("FU","fu"),("2U","2u"),("3U","3u"),("ClockW","clockwise"),("AClockW","anticlockwise")):
        tri = _extract_label_triple(block, label)
        w,p,s = _triple(tri)
        d[f"{key}_rec"] = tri; d[f"{key}_wins"] = w; d[f"{key}_places"] = p; d[f"{key}_starts"] = s
    m = re.search(r"(?mi)^DLS\s*$\s*^\s*(\d+)", block)
    if m: d["dls"] = int(m.group(1))
    m = re.search(r"(?mi)^DLW\s*$\s*^\s*(\d+)", block)
    if m: d["dlw"] = int(m.group(1))
    m = re.search(r"(?mi)^ROI\s*$\s*^\s*([\d.]+)%", block)
    if m: d["roi"] = _f(m.group(1))/100
    d["recent_runs"] = _parse_recent_runs(block)
    ratings = [int(r["ohr"]) for r in d["recent_runs"] if r.get("ohr")]
    if ratings: d["latest_ohr"] = ratings[0]
    return d


def parse(raw: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    header = parse_header(raw)
    runners = parse_summary(raw)
    if not runners:
        return header, [], ["Could not locate the harness runners table."]
    blocks = _runner_blocks(raw, runners)
    for r in runners:
        block = blocks.get(r["tab"])
        if block:
            r.update(_parse_block(block, r))
        else:
            warnings.append(f"No detail block found for #{r['tab']} {r['horse']}.")
        r.setdefault("form", "")
        r.setdefault("driver_win", .10); r.setdefault("driver_place", .32)
        r.setdefault("trainer_win", .10); r.setdefault("trainer_place", .32)
        r.setdefault("driver_horse_win", 0.0); r.setdefault("driver_horse_place", 0.0); r.setdefault("driver_horse_n", 0)
        r.setdefault("driver_trainer_win", 0.0); r.setdefault("driver_trainer_place", 0.0); r.setdefault("driver_trainer_n", 0)
        r.setdefault("dls", 14); r.setdefault("recent_runs", [])
        for key in ("career","12m","course","distance","course_distance"):
            r.setdefault(f"{key}_rec", "0-0-0"); r.setdefault(f"{key}_wins", 0); r.setdefault(f"{key}_places", 0); r.setdefault(f"{key}_starts", 0)
    active = [r for r in runners if not r.get("scratched")]
    if any(len(r.get("recent_runs", [])) < 3 for r in active):
        warnings.append("Some active runners have fewer than three parsed recent starts; confidence is reduced.")
    if not header.get("distance_m"):
        warnings.append("Race distance was not parsed; distance matching will be limited.")
    return header, runners, warnings
