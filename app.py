"""Streamlit interface for RaceParsePredict.

Paste a Racing & Sports Enhanced Form page, parse the runners, and run the
existing market + fundamentals + finishing-order model in a browser UI.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

import model
import rs_parser

st.set_page_config(
    page_title="RaceParsePredict",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.25rem; padding-bottom: 3rem;}
    div[data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,.22);
        border-radius: .7rem;
        padding: .55rem .8rem;
    }
    .race-hero {
        padding: 1rem 1.1rem;
        border-radius: .85rem;
        background: linear-gradient(135deg, rgba(61,90,254,.16), rgba(0,0,0,0));
        border: 1px solid rgba(128,128,128,.22);
        margin-bottom: 1rem;
    }
    .winner-card {
        padding: 1rem 1.2rem;
        border: 1px solid rgba(46, 204, 113, .35);
        border-radius: .8rem;
        background: rgba(46, 204, 113, .08);
        margin: .4rem 0 1rem 0;
    }
    .small-muted {opacity: .72; font-size: .9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

PARSED_COLS = [
    ("tab", "No"), ("horse", "Horse"), ("wt", "Wt"), ("bp", "BP"),
    ("jockey", "Jockey"), ("claim", "Claim"), ("jrat", "JRat"),
    ("trainer", "Trainer"), ("trat", "TRat"), ("tab_odds", "TAB$"),
    ("bf_odds", "BF$"), ("ohr", "OHR"), ("form5", "Form"),
    ("last_fin", "LastFin"), ("dslr", "DSLR"), ("runs_this_prep", "Prep"),
    ("age", "Age"), ("sex", "Sex"), ("sire", "Sire"),
    ("jky_win", "JkyW%"), ("trn_win", "TrnW%"), ("jt_win", "J/T%"),
    ("Car_rec", "Career"), ("12m_rec", "12m"), ("Crs_rec", "Course"),
    ("Dist_rec", "Dist"), ("CrsDist_rec", "C&D"), ("Good_rec", "Good"),
    ("Soft_rec", "Soft"), ("Heavy_rec", "Heavy"),
    ("career_pm_k", "CarPM$k"), ("pm_12m", "12mPM$"),
    ("ls_margin", "LS Mgn"), ("ls_dist", "LS Dist"), ("ls_class", "LS Cls"),
    ("ls_sp", "LS SP"), ("gear_change", "Gear"), ("had_trial", "Trial"),
]

PCT_KEYS = {"jky_win", "trn_win", "jt_win"}


def reset_app() -> None:
    st.session_state["paste_input"] = ""
    for key in ("header", "runners", "warnings", "result"):
        st.session_state.pop(key, None)


def race_title(header: dict[str, Any]) -> str:
    bits = []
    if header.get("track"):
        bits.append(str(header["track"]))
    if header.get("race_name"):
        bits.append(str(header["race_name"]))
    return " — ".join(bits) or "Parsed race"


def race_subtitle(header: dict[str, Any]) -> str:
    left = " ".join(
        str(x) for x in (
            f"{header.get('distance_m')}m" if header.get("distance_m") else "",
            header.get("surface", ""),
            header.get("going", ""),
        ) if x
    )
    bits = [left, header.get("prize", ""), header.get("date", "")]
    return " | ".join(str(x) for x in bits if x)


def parsed_dataframe(runners: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for runner in runners:
        row: dict[str, Any] = {}
        for key, label in PARSED_COLS:
            value = runner.get(key, "")
            if isinstance(value, bool):
                value = "Y" if value else ""
            elif key in PCT_KEYS and isinstance(value, (int, float)):
                value = value * 100
            row[label] = value
        rows.append(row)
    return pd.DataFrame(rows)


def prediction_dataframe(
    runners: list[dict[str, Any]], result: dict[str, Any]
) -> pd.DataFrame:
    rows = []
    for rank, i in enumerate(result["order"], start=1):
        p_win = float(result["p_win"][i])
        rows.append({
            "Pred": rank,
            "No": runners[i]["tab"],
            "Horse": runners[i]["horse"],
            "Mkt%": float(result["p_mkt"][i]) * 100,
            "Fund%": float(result["p_fund"][i]) * 100,
            "Win%": p_win * 100,
            "Top3%": float(result["top3"][i]) * 100,
            "E[pos]": float(result["exp_pos"][i]),
            "Fair$": (1 / p_win) if p_win > 0 else float("inf"),
            "BF$": float(runners[i]["bf_odds"]),
            "EV": float(result["ev_win"][i]),
            "Conf": int(result["conf"][i]),
            "Recommendation": result["recs"][i],
        })
    return pd.DataFrame(rows)


def dataframe_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


for key, default in (
    ("header", {}),
    ("runners", []),
    ("warnings", []),
    ("result", None),
):
    st.session_state.setdefault(key, default)

st.markdown(
    """
    <div class="race-hero">
      <h1 style="margin:0">🏇 RaceParsePredict</h1>
      <div class="small-muted">Racing & Sports Enhanced Form parser + race prediction model</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Model settings")
    alpha = st.slider(
        "Market weight α",
        min_value=0.50,
        max_value=0.99,
        value=float(model.MARKET_ALPHA),
        step=0.01,
        help="Higher values make the final probability follow market prices more closely.",
    )
    sims = st.select_slider(
        "Monte Carlo simulations",
        options=[5_000, 10_000, 20_000, 30_000, 50_000],
        value=30_000,
        help="More simulations reduce sampling noise but take longer.",
    )
    seed = st.number_input("Random seed", min_value=0, max_value=999_999, value=42, step=1)
    st.divider()
    st.caption(
        "Pipeline: Shin de-vig → market/fundamental blend → discounted "
        "Plackett–Luce finishing-order simulation."
    )
    st.caption("This is a decision-support model, not a guarantee of race outcomes.")

paste_tab, parsed_tab, pred_tab, explain_tab, method_tab = st.tabs(
    ["1 · Paste Data", "2 · Parsed Data", "3 · Prediction", "4 · Explanations", "Method"]
)

with paste_tab:
    st.subheader("Paste the full Racing & Sports Enhanced Form page")
    st.caption("On the source page: select all → copy → paste into the box below.")
    pasted = st.text_area(
        "Race data",
        key="paste_input",
        height=430,
        placeholder="Paste Racing & Sports Enhanced Form text here…",
        label_visibility="collapsed",
    )
    c1, c2, c3 = st.columns([1, 1, 5])
    with c1:
        parse_clicked = st.button("Parse race ▶", type="primary", use_container_width=True)
    with c2:
        st.button("Clear", on_click=reset_app, use_container_width=True)

    if parse_clicked:
        if len(pasted.strip()) < 200:
            st.error("The pasted text looks too short. Paste the full Enhanced Form page and try again.")
        else:
            try:
                header, runners, warnings = rs_parser.parse(pasted)
                st.session_state["header"] = header
                st.session_state["runners"] = runners
                st.session_state["warnings"] = warnings
                st.session_state["result"] = None
                if runners:
                    st.success(f"Parsed {len(runners)} runners. Open **2 · Parsed Data** to verify them.")
                else:
                    st.error("No runners were found in the pasted text.")
            except Exception as exc:
                st.exception(exc)

    if st.session_state["runners"]:
        st.info(
            f"Current race: **{race_title(st.session_state['header'])}** — "
            f"{len(st.session_state['runners'])} runners parsed."
        )
    if st.session_state["warnings"]:
        with st.expander(f"Parser warnings ({len(st.session_state['warnings'])})"):
            for warning in st.session_state["warnings"]:
                st.warning(warning)

with parsed_tab:
    runners = st.session_state["runners"]
    header = st.session_state["header"]
    if not runners:
        st.info("Parse a race in **1 · Paste Data** first.")
    else:
        st.subheader(race_title(header))
        st.caption(race_subtitle(header))
        parsed_df = parsed_dataframe(runners)
        st.dataframe(
            parsed_df,
            use_container_width=True,
            hide_index=True,
            height=520,
            column_config={
                "JkyW%": st.column_config.NumberColumn(format="%.1f%%"),
                "TrnW%": st.column_config.NumberColumn(format="%.1f%%"),
                "J/T%": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
        st.download_button(
            "Download parsed data (CSV)",
            data=dataframe_csv_bytes(parsed_df),
            file_name="parsed_race.csv",
            mime="text/csv",
        )

with pred_tab:
    runners = st.session_state["runners"]
    header = st.session_state["header"]
    if not runners:
        st.info("Parse and verify a race first.")
    else:
        st.subheader("Run prediction")
        st.caption(
            f"Using market weight α={alpha:.2f}, {int(sims):,} simulations, seed {int(seed)}."
        )
        if st.button("Predict race ▶", type="primary", key="predict_button"):
            try:
                with st.spinner("Running prediction model…"):
                    st.session_state["result"] = model.predict(
                        runners,
                        header,
                        alpha=float(alpha),
                        sims=int(sims),
                        seed=int(seed),
                    )
            except Exception as exc:
                st.exception(exc)

        result = st.session_state["result"]
        if result is not None:
            pred_df = prediction_dataframe(runners, result)
            winner = pred_df.iloc[0]
            st.markdown(
                f"""
                <div class="winner-card">
                  <div class="small-muted">MODEL TOP PICK</div>
                  <h2 style="margin:.1rem 0">#{int(winner['No'])} {winner['Horse']}</h2>
                  <b>Win {winner['Win%']:.1f}%</b> · Top 3 {winner['Top3%']:.1f}% ·
                  Fair ${winner['Fair$']:.2f} · EV {winner['EV']:.2f} · Confidence {int(winner['Conf'])}/9
                </div>
                """,
                unsafe_allow_html=True,
            )
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Overall confidence", f"{result['overall_conf']}/9")
            m2.metric("TAB overround", f"{result['overround_tab']:.3f}")
            m3.metric("Shin z", f"{result['shin_z']:.4f}")
            m4.metric("Betfair book", f"{result['book_bf']:.3f}")

            st.dataframe(
                pred_df,
                use_container_width=True,
                hide_index=True,
                height=520,
                column_config={
                    "Mkt%": st.column_config.NumberColumn(format="%.1f%%"),
                    "Fund%": st.column_config.NumberColumn(format="%.1f%%"),
                    "Win%": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                    "Top3%": st.column_config.NumberColumn(format="%.1f%%"),
                    "E[pos]": st.column_config.NumberColumn(format="%.2f"),
                    "Fair$": st.column_config.NumberColumn(format="$%.2f"),
                    "BF$": st.column_config.NumberColumn(format="$%.2f"),
                    "EV": st.column_config.NumberColumn(format="%.2f"),
                    "Conf": st.column_config.NumberColumn("Conf 0–9", format="%d"),
                },
            )
            st.download_button(
                "Download prediction (CSV)",
                data=dataframe_csv_bytes(pred_df),
                file_name="race_prediction.csv",
                mime="text/csv",
            )

with explain_tab:
    runners = st.session_state["runners"]
    result = st.session_state["result"]
    if result is None or not runners:
        st.info("Run the model in **3 · Prediction** first.")
    else:
        st.subheader(f"Runner explanations · overall confidence {result['overall_conf']}/9")
        for rank, i in enumerate(result["order"], start=1):
            runner = runners[i]
            title = (
                f"{rank}. #{runner['tab']} {runner['horse']} — "
                f"Win {result['p_win'][i] * 100:.1f}% · Conf {result['conf'][i]}/9"
            )
            with st.expander(title, expanded=(rank <= 3)):
                st.markdown(f"**Recommendation:** {result['recs'][i]}")
                st.text(result["why"][i])

with method_tab:
    st.subheader("How the model works")
    st.markdown(
        """
        The app keeps the prediction engine supplied in the original desktop program:

        1. **Market probabilities** — TAB fixed odds are de-vigged with a Shin-style adjustment and combined with normalized Betfair prices.
        2. **Fundamental score** — official rating, weight, career/distance/going records, jockey/trainer figures, last-start finish, freshness and R&S ratings are standardized and combined.
        3. **Benter-style blend** — market and fundamental probabilities are combined in log-probability space. The sidebar **α** controls how strongly the market is weighted.
        4. **Finishing-order simulation** — a discounted Plackett–Luce process simulates the complete finishing order and produces expected position and Top-3 probability.
        5. **Value screen** — Betfair odds are compared with model win probability to calculate EV and assign a recommendation.

        **Important:** confidence and EV are model outputs based on the pasted data and market prices. They are not guarantees and should not be treated as certain outcomes.
        """
    )
