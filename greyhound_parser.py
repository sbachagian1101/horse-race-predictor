"""Racing & Sports greyhound Enhanced Form paste parser.

The parser is intentionally tolerant. It accepts the Markdown-ish text produced
when a Racing & Sports page is pasted into ChatGPT as well as ordinary copied
page text. The summary field is authoritative for runner/weight/trainer/odds;
detail blocks enrich each runner with box history, track/distance statistics,
trainer form and recent runs.
"""
from __future__ import annotations

import re
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        s = str(value).replace("$", "").replace(",", "").replace("sec", "").strip()
        return float(s)
    except Exception:
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _triple(value: str) -> tuple[int, int, int]:
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", value or "")
    if not m:
        return 0, 0, 0
    return tuple(int(x) for x in m.groups())


def _clean_md(text: str) -> str:
    """Remove Markdown link/bold syntax while preserving line structure."""
    text = text.replace("\xa0", " ").replace("\u2003", " ").replace("\u2002", " ")
    text = text.replace("\\-", "-").replace("\\:", ":").replace("\\&", "&")
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = text.replace("**", "").replace("***", "").replace("__", "")
    text = re.sub(r"^[#>*-]+\s*", "", text, flags=re.M)
    return "\n".join(line.strip() for line in text.splitlines())


def parse_header(raw: str) -> dict[str, Any]:
    t = _clean_md(raw)
    h: dict[str, Any] = {}
    m = re.search(r"^(.+?)\s+Form Guide\s*\(Race\s*(\d+)\)", t, re.M | re.I)
    if m:
        h["track"], h["race_no"] = m.group(1).strip(), int(m.group(2))
    else:
        m = re.search(r"^(.+?)\s+Form Guide", t, re.M | re.I)
        if m:
            h["track"] = m.group(1).strip()
    m = re.search(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(.+?\d{4})$", t, re.M | re.I)
    if m:
        h["date"] = f"{m.group(1)}, {m.group(2)}"
    m = re.search(r"^(\d{1,2}:\d{2})\s*$", t, re.M)
    if m:
        h["time"] = m.group(1)
    m = re.search(r"\(local\)\s*\n\s*([A-Z0-9][A-Z0-9 '&+()\-/\.]+)\s*\n\s*Type:", t, re.S)
    if m:
        h["race_name"] = m.group(1).strip()
    m = re.search(r"Type:\s*([^\n]+?)(?:\s+Fastest Time:|$)", t, re.I)
    if m:
        h["race_type"] = m.group(1).strip()
    m = re.search(r"Fastest Time:\s*([0-9:.]+)\s+([^\n]+)", t, re.I)
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


def _parse_summary_markdown(raw: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not re.match(r"^\|\s*\d{1,2}\s*\|", line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        tab = _i(re.sub(r"\D", "", cells[0]))
        if not 1 <= tab <= 10:
            continue
        name_m = re.search(r"\[\**([^\]]+?)\**\]\(", cells[1])
        trainer_m = re.search(r"\[\**([^\]]+?)\**\]\(", cells[3])
        name = (name_m.group(1) if name_m else re.sub(r"[\[\]*]", "", cells[1])).strip().upper()
        trainer = (trainer_m.group(1) if trainer_m else re.sub(r"[\[\]*]", "", cells[3])).strip().upper()
        if not name or name.lower().startswith("http"):
            continue
        weight = _f(cells[2])
        scratch = any("scr" in c.lower() for c in cells[4:])
        odds = 999.0
        for c in reversed(cells[4:]):
            c2 = re.sub(r"[*$]", "", c).strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", c2):
                odds = _f(c2, 999.0)
                break
        out.append({"tab": tab, "box": tab if tab <= 8 else 0, "horse": name,
                    "weight": weight, "trainer": trainer, "scratched": scratch,
                    "tab_odds": odds})
    return out


def _parse_summary_plain(raw: str) -> list[dict[str, Any]]:
    t = _clean_md(raw)
    out: list[dict[str, Any]] = []
    for line in t.splitlines():
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) >= 4 and re.fullmatch(r"\d{1,2}", parts[0]):
            tab = int(parts[0])
            if 1 <= tab <= 10 and re.search(r"[A-Za-z]", parts[1]):
                scratch = any("scr" in p.lower() for p in parts)
                nums = [_f(p, -1) for p in parts[2:] if re.fullmatch(r"\$?\d+(?:\.\d+)?", p)]
                weight = nums[0] if nums else 0.0
                odds = nums[-1] if nums and not scratch else 999.0
                trainer = parts[3] if len(parts) > 3 else ""
                out.append({"tab": tab, "box": tab if tab <= 8 else 0,
                            "horse": parts[1].upper(), "weight": weight,
                            "trainer": trainer.upper(), "scratched": scratch,
                            "tab_odds": odds})
    return out


def parse_summary(raw: str) -> list[dict[str, Any]]:
    runners = _parse_summary_markdown(raw)
    if not runners:
        runners = _parse_summary_plain(raw)
    seen, dedup = set(), []
    for r in runners:
        if r["tab"] not in seen:
            dedup.append(r)
            seen.add(r["tab"])
    scratched_boxes = sorted(r["tab"] for r in dedup if r["tab"] <= 8 and r["scratched"])
    reserve_active = [r for r in dedup if r["tab"] > 8 and not r["scratched"]]
    for r, box in zip(reserve_active, scratched_boxes):
        r["box"] = box
        r["reserve_into_box"] = True
    return dedup


def _runner_blocks(raw: str, runners: list[dict[str, Any]]) -> dict[int, str]:
    t = _clean_md(raw)
    starts: list[tuple[int, int]] = []
    for r in runners:
        pat = re.compile(rf"(?mi)^([fFxX0-9]{{3,8}})\s*\n\s*\$?([0-9]+(?:\.[0-9]+)?)\s*\n\s*{re.escape(r['horse'])}\s+\d+yo\b")
        m = pat.search(t)
        if m:
            starts.append((m.start(), r["tab"]))
    starts.sort()
    blocks: dict[int, str] = {}
    for idx, (pos, tab) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(t)
        blocks[tab] = t[pos:end]
    return blocks


def _extract_label_triple(block: str, label: str) -> str:
    m = re.search(rf"(?mi)^{re.escape(label)}\s*$\s*^\s*(\d+\s*-\s*\d+\s*-\s*\d+)\s*$", block)
    return re.sub(r"\s+", "", m.group(1)) if m else "0-0-0"


def _parse_recent_runs(block: str) -> list[dict[str, Any]]:
    lines = [ln.strip() for ln in block.splitlines()]
    runs: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        if "Margin" not in line or "Distance" not in line or "Runner Time" not in line:
            continue
        r: dict[str, Any] = {}
        for j in range(max(0, i - 10), i):
            m = re.fullmatch(r"(\d+)\s+of\s+(\d+)", lines[j], re.I)
            if m:
                r["finish"], r["field"] = int(m.group(1)), int(m.group(2))
            m = re.search(r"(\d+)(?:st|nd|rd|th)\s*([+-]?\d+(?:\.\d+)?)", lines[j], re.I)
            if m:
                r["mrk_rank"], r["mrk_delta"] = int(m.group(1)), _f(m.group(2))
        m = re.search(r"(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", line)
        if m: r["date"] = m.group(1)
        m = re.search(r"([A-Za-z .'-]+)\s*\(AUSTRALIA\):", line, re.I)
        if m: r["track"] = m.group(1).strip().upper()
        specs = {
            "margin": r"Margin\s*([\d.]+)L", "distance": r"Distance\s*(\d+)m",
            "race_time": r"Race Time\s*([\d.]+)", "bom": r"BOM\s*([\d.]+)sec",
            "bom_adj": r"BOM Time Adj\s*([+-]?\d+(?:\.\d+)?)sec",
            "runner_time": r"Runner Time\s*([\d.]+)", "first_split": r"1st Split\s*([\d.]+)",
            "prior_box": r"\bBP\s*(\d+)", "sp": r"\bSP\s*\$([\d.]+)"}
        for key, pat in specs.items():
            m = re.search(pat, line, re.I)
            if m:
                r[key] = _i(m.group(1)) if key in {"distance", "prior_box"} else _f(m.group(1))
        m = re.search(r"Class\s*(.*?)\s*Prize\b", line, re.I)
        if m: r["class"] = m.group(1).strip()
        m = re.search(r"Stewards\s*(.*?)(?=\s*Inrunning Position|\s*Runner Sectional|$)", line, re.I)
        if m: r["stewards"] = m.group(1).strip().rstrip(".")
        m = re.search(r"(\d+)(?:st|nd|rd|th) Place on settling\s+(\d+)(?:st|nd|rd|th) Place on turn", line, re.I)
        if m:
            r["settle_pos"], r["turn_pos"] = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r"Inrunning Position\s*(\d+)(?:st|nd|rd|th) Place on settling", line, re.I)
            if m: r["settle_pos"] = int(m.group(1))
        m = re.search(r"L1m\s*\([\d.]+\s+(\d+)(?:st|nd|rd|th)\)", line, re.I)
        if m: r["split_rank"] = int(m.group(1))
        runs.append(r)
    return runs


def _parse_block(block: str, runner: dict[str, Any]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    m = re.search(r"(?mi)^([fFxX0-9]{3,8})\s*$\s*^\$?([0-9]+(?:\.[0-9]+)?)\s*$", block)
    if m:
        d["form"] = m.group(1).lower()
        d["bf_odds"] = _f(m.group(2), 999.0)
    m = re.search(rf"(?mi)^{re.escape(runner['horse'])}\s+(\d+)yo\s+([A-Z/]+)\s+([A-Z]+)", block)
    if m:
        d["age"], d["colour"], d["sex"] = int(m.group(1)), m.group(2), m.group(3)
    m = re.search(r"(?mi)^Tra L50\s*$\s*^(\d+)%-(\d+)%-(\d+)\s*$", block)
    if m:
        d["trainer_win"] = int(m.group(1)) / 100
        d["trainer_place"] = int(m.group(2)) / 100
        d["trainer_l50_n"] = int(m.group(3))
    m = re.search(r"(?mi)^Tra/Dist Best Time\s*$\s*^([\d.]+|-)\s*$", block)
    if m and m.group(1) != "-":
        d["tra_dist_best"] = _f(m.group(1))
    box_stats = {b: {"wins": 0, "places23": 0, "starts": 0} for b in range(1, 9)}
    for label, key in (("Win", "wins"), ("2nd/3rd", "places23"), ("Starts", "starts")):
        m = re.search(rf"(?mi)^\|?\s*{re.escape(label)}\s*\|\s*([\d\s|]+)\|?\s*$", block)
        if m:
            nums = [int(x) for x in re.findall(r"\d+", m.group(1))][:8]
            for b, val in enumerate(nums, start=1): box_stats[b][key] = val
    d["box_stats"] = box_stats
    for label, key in (("Car", "career"), ("12m", "12m"), ("Crs", "course"),
                       ("Dist", "distance"), ("Crs & Dist", "course_distance"),
                       ("FU", "fu"), ("2U", "2u"), ("3U", "3u")):
        tri = _extract_label_triple(block, label)
        w, p, s = _triple(tri)
        d[f"{key}_rec"], d[f"{key}_wins"], d[f"{key}_places23"], d[f"{key}_starts"] = tri, w, p, s
    for label, key in (("DLS", "dls"), ("ROI", "roi")):
        m = re.search(rf"(?mi)^{label}\s*$\s*^\s*([^\n]+)", block)
        if m:
            d[key] = _f(m.group(1).replace("%", "")) / 100 if label == "ROI" else _i(re.search(r"\d+", m.group(1)).group(0)) if re.search(r"\d+", m.group(1)) else 0
    m = re.search(r"(?mi)^DLW\s*$\s*^\s*(\d+)", block)
    if m: d["dlw"] = int(m.group(1))
    d["recent_runs"] = _parse_recent_runs(block)
    return d


def parse(raw: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    header = parse_header(raw)
    runners = parse_summary(raw)
    if not runners:
        return header, [], ["Could not locate the greyhound runners table."]
    blocks = _runner_blocks(raw, runners)
    for r in runners:
        if r["tab"] in blocks:
            r.update(_parse_block(blocks[r["tab"]], r))
        else:
            warnings.append(f"No detail block found for #{r['tab']} {r['horse']}.")
        r.setdefault("form", "")
        r.setdefault("bf_odds", r.get("tab_odds", 999.0))
        r.setdefault("trainer_win", 0.10); r.setdefault("trainer_place", 0.35)
        r.setdefault("tra_dist_best", 0.0); r.setdefault("dls", 14); r.setdefault("recent_runs", [])
        r.setdefault("box_stats", {b: {"wins": 0, "places23": 0, "starts": 0} for b in range(1, 9)})
        for key in ("career", "12m", "course", "distance", "course_distance"):
            r.setdefault(f"{key}_rec", "0-0-0"); r.setdefault(f"{key}_wins", 0)
            r.setdefault(f"{key}_places23", 0); r.setdefault(f"{key}_starts", 0)
    active = [r for r in runners if not r.get("scratched")]
    if any(r.get("box", 0) == 0 for r in active):
        warnings.append("One or more active reserves could not be assigned to a vacant box.")
    if any(len(r.get("recent_runs", [])) < 3 for r in active):
        warnings.append("Some active runners have fewer than three parsed recent runs; their model confidence is reduced.")
    return header, runners, warnings
