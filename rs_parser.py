"""
rs_parser.py - Racing & Sports "Enhanced Form" paste parser
============================================================
Extracts race header + full per-runner data from a raw copy/paste of an
R&S enhanced form page (racingandsports.com.au).

Robustness strategy:
  1. The runners summary table (Tab/Horse/WT/BP/Jockey/JRat/Trainer/TRat/odds)
     is the authoritative source for the core fields.
  2. Per-horse detail blocks (split on the `<tab>\n<form>\nbetfair$X` marker)
     enrich each runner with Betfair odds, form string, OHR, L50 strike
     rates, WPS filter blocks, DSLR, last-start details, prize money etc.
  3. Every field degrades gracefully to a default if missing, so a partial
     paste still parses.
"""

import re

# Label order of the R&S "Filters WPS" block (values are W-P-S triples)
WPS_LABELS = ["Car", "12m", "Crs", "Dist", "CrsDist", "Firm", "Good", "Soft",
              "Heavy", "AW", "Turf", "G1", "G2", "G3", "LR", "FU", "2U", "3U",
              "ClockW", "AClockW", "Dirt", "Sand"]

FLOAT = r"[\d.]+"


def _wps(triple):
    """'4-6-25' -> (wins, places(2nd+3rd), starts, win%, place%)."""
    try:
        w, p, s = (int(x) for x in triple.split("-"))
    except Exception:
        return 0, 0, 0, 0.0, 0.0
    st = max(s, 1)
    return w, p, s, w / st, (w + p) / st


def _f(x, default=0.0):
    try:
        return float(str(x).replace("$", "").replace(",", ""))
    except Exception:
        return default


def parse_race_header(text):
    hdr = {}
    m = re.search(r"^(\d{3,4})m\s+(TURF|AW|SAND|DIRT|POLY)\s+(\w+)\s*(\d*)",
                  text, re.M)
    if m:
        hdr["distance_m"] = int(m.group(1))
        hdr["surface"] = m.group(2)
        hdr["going"] = (m.group(3) + " " + m.group(4)).strip()
    m = re.search(r"^(.*?(?:Handicap|Plate|Stakes|Cup|Trophy|Hcp).*?)$",
                  text, re.M)
    if m:
        hdr["race_name"] = m.group(1).strip()
    m = re.search(r"Type:\s*(\S+)", text)
    if m:
        hdr["race_class"] = m.group(1)
    m = re.search(r"AUD \$([\d,]+)", text)
    if m:
        hdr["prize"] = "AUD $" + m.group(1)
    m = re.search(r"(\w+day),?\s+(\d{1,2}\w{2}\s+\w+\s+\d{4})", text)
    if m:
        hdr["date"] = m.group(0)
    m = re.search(r"^(.+?) Form Guide", text, re.M)
    if m:
        hdr["track"] = m.group(1).replace("Enhanced", "").strip()
    m = re.search(r"SOT:\s*(\w+)", text)
    if m:
        hdr["sot"] = m.group(1)
    return hdr


def parse_summary_table(text):
    """Parse the runners table. Rows are tab-separated:
    Tab, Horse, WT, BP, Jockey, JRat, Trainer, TRat, [Bet365], Tab-odds
    JRat/TRat may be prefixed with 'H ' (highlight)."""
    runners = []
    # locate section between the column header line and 'Explanations'
    m = re.search(r"Tab\s+Horse\s+WT\s+BP.*?\n(.*?)(?:\nExplanations|\Z)",
                  text, re.S)
    body = m.group(1) if m else text
    for line in body.splitlines():
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) >= 8 and re.fullmatch(r"\d{1,2}", parts[0]):
            r = {
                "tab": int(parts[0]),
                "horse": parts[1].upper(),
                "wt": _f(parts[2]),
                "bp": int(_f(parts[3])),
                "jockey": re.sub(r"\s*\(a\d+\)", "", parts[4]).strip(),
                "claim": (re.search(r"\(a(\d+(?:\.\d+)?)\)", parts[4]) or
                          [None, "0"])[1] if "(a" in parts[4] else "0",
                "jrat": _f(re.sub(r"^H\s*", "", parts[5])),
                "trainer": parts[6],
                "trat": _f(re.sub(r"^H\s*", "", parts[7])),
            }
            r["claim"] = _f(r["claim"])
            # last numeric token on the line = TAB fixed odds
            nums = [p for p in parts[8:] if re.fullmatch(FLOAT, p)]
            r["tab_odds"] = _f(nums[-1], 999.0) if nums else 999.0
            runners.append(r)
    return runners


def _split_detail_blocks(text, runners):
    """Detail blocks start with: <tab#>\n<form-string>\nbetfair$<odds>."""
    marker = re.compile(
        r"^(\d{1,2})\n([\dx0]+)\nbetfair\$(" + FLOAT + r")\s*$", re.M)
    hits = list(marker.finditer(text))
    blocks = {}
    for i, h in enumerate(hits):
        tab = int(h.group(1))
        if tab not in {r["tab"] for r in runners}:
            continue
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        blocks[tab] = {"form": h.group(2), "bf_odds": _f(h.group(3), 999.0),
                       "text": text[h.start():end]}
    return blocks


def _parse_block(b):
    """Enrich one runner from its detail block."""
    t = b["text"]
    d = {"form5": b["form"], "bf_odds": b["bf_odds"]}

    # last-start finish from form string (rightmost digit; 0 => 10th+)
    digits = re.sub(r"[^0-9]", "", b["form"])
    d["last_fin"] = (10 if digits[-1] == "0" else int(digits[-1])) \
        if digits else 10

    m = re.search(r"(\d+)yo\s+([A-Z/]+)\s+(\w+)", t)
    if m:
        d["age"], d["colour"], d["sex"] = int(m.group(1)), m.group(2), m.group(3)

    m = re.search(r"Sire([A-Z' .()-]+?)\nDam", t)
    if m:
        d["sire"] = m.group(1).strip()

    # Jockey/Trainer Last50: first two 'Last50' hits are jockey then trainer
    l50 = re.findall(r"Last50(\d+)%-(\d+)%-(\d+)", t)
    if len(l50) >= 1:
        d["jky_win"], d["jky_place"] = int(l50[0][0]) / 100, int(l50[0][1]) / 100
    if len(l50) >= 2:
        d["trn_win"], d["trn_place"] = int(l50[1][0]) / 100, int(l50[1][1]) / 100

    m = re.search(r"J/T(\d+)%-(\d+)%-(\d+)", t)
    if m:
        d["jt_win"], d["jt_runs"] = int(m.group(1)) / 100, int(m.group(3))

    # WPS filter block between 'FiltersWPS' and 'Facts'. R&S concatenates
    # each value with the NEXT label on the same line ("4-6-2512m" =
    # Car value 4-6-25 + label 12m), so strip known label suffixes in order.
    RAW_LABELS = ["Car", "12m", "Crs", "Dist", "Crs & Dist", "Firm", "Good",
                  "Soft", "Heavy", "AW", "Turf", "G1", "G2", "G3", "LR", "FU",
                  "2U", "3U", "ClockW", "AClockW", "Dirt", "Sand"]
    m = re.search(r"FiltersWPS.*?\nCar\n(.*?)\nFacts", t, re.S)
    if m:
        lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
        for k, line in enumerate(lines):
            if k >= len(RAW_LABELS):
                break
            label = WPS_LABELS[k]                       # normalized key
            nxt = RAW_LABELS[k + 1] if k + 1 < len(RAW_LABELS) else None
            val = line
            if nxt and val.endswith(nxt):
                val = val[: -len(nxt)]
            tri = re.fullmatch(r"\d+-\d+-\d+", val)
            if not tri:
                # fallback: non-greedy triple at line start
                tri = re.match(r"(\d+-\d+-\d+?)(?=\D|$)", val)
                val = tri.group(1) if tri else "0-0-0"
            w, p, s, wr, pr = _wps(val)
            d[f"{label}_rec"] = val
            d[f"{label}_win"] = wr
            d[f"{label}_plc"] = pr
            d[f"{label}_starts"] = s

    m = re.search(r"Days Since Last Run:\s*(\d+)\s*days\s*\((\d+)U\)", t)
    if m:
        d["dslr"], d["runs_this_prep"] = int(m.group(1)), int(m.group(2))

    m = re.search(r"Car PM\n\$(" + FLOAT + r")k", t)
    if m:
        d["career_pm_k"] = _f(m.group(1))
    m = re.search(r"12m PM\n\$([\d,]+)", t)
    if m:
        d["pm_12m"] = _f(m.group(1))

    # current OHR = first 'NN\nOHR' occurrence (most recent run)
    m = re.search(r"(\d{2,3})\nOHR", t)
    if m:
        d["ohr"] = int(m.group(1))

    # last start details (first Results entry)
    m = re.search(r"Margin (" + FLOAT + r")L Distance (\d+)m.*?"
                  r"Class (\S+).*?SP \$(" + FLOAT + r")", t, re.S)
    if m:
        d["ls_margin"] = _f(m.group(1))
        d["ls_dist"] = int(m.group(2))
        d["ls_class"] = m.group(3)
        d["ls_sp"] = _f(m.group(4))

    d["gear_change"] = bool(re.search(r"Blinkers ON|blinker on", t[:3000]))
    d["had_trial"] = "BT Results" in t
    return d


def parse(text):
    """Main entry. Returns (header_dict, list-of-runner-dicts, warnings)."""
    warnings = []
    header = parse_race_header(text)
    runners = parse_summary_table(text)
    if not runners:
        warnings.append("Could not locate runners summary table.")
        return header, [], warnings

    blocks = _split_detail_blocks(text, runners)
    for r in runners:
        b = blocks.get(r["tab"])
        if b:
            r.update(_parse_block(b))
        else:
            warnings.append(f"No detail block found for #{r['tab']} "
                            f"{r['horse']} - core fields only.")
        # defaults for anything missing
        r.setdefault("bf_odds", r.get("tab_odds", 999.0))
        r.setdefault("ohr", 0)
        r.setdefault("dslr", 30)
        r.setdefault("runs_this_prep", 1)
        r.setdefault("last_fin", 10)
        r.setdefault("jky_win", 0.05)
        r.setdefault("trn_win", 0.05)
        for lbl in ("Car", "Dist", "Good", "Soft", "Crs"):
            r.setdefault(f"{lbl}_win", 0.0)
            r.setdefault(f"{lbl}_plc", 0.0)
            r.setdefault(f"{lbl}_starts", 0)
            r.setdefault(f"{lbl}_rec", "0-0-0")
        r.setdefault("form5", "")
        r.setdefault("career_pm_k", 0.0)
        r.setdefault("pm_12m", 0.0)
    if any(r["ohr"] == 0 for r in runners):
        warnings.append("One or more runners missing OHR - fundamental model "
                        "will lean on other factors for them.")
    return header, runners, warnings
