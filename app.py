"""Streamlit harness-racing predictor for Racing & Sports Enhanced Form paste data."""
from __future__ import annotations
import io
import pandas as pd
import streamlit as st
import harness_parser as parser
import harness_model as model

st.set_page_config(page_title="HarnessParsePredict", page_icon="🏇", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container{padding-top:1.25rem;padding-bottom:3rem}.hero{padding:1rem 1.1rem;border-radius:.85rem;background:linear-gradient(135deg,rgba(244,134,53,.17),rgba(0,0,0,0));border:1px solid rgba(128,128,128,.22);margin-bottom:1rem}.pick{padding:1rem 1.2rem;border:1px solid rgba(46,204,113,.35);border-radius:.8rem;background:rgba(46,204,113,.08);margin:.4rem 0 1rem}.muted{opacity:.72;font-size:.9rem}div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.22);border-radius:.7rem;padding:.55rem .8rem}
</style>""", unsafe_allow_html=True)

def reset_app():
    st.session_state["paste_input"]=""
    for k in ("header","runners","warnings","result"): st.session_state.pop(k,None)

def race_title(h):
    bits=[str(h.get("track","")).strip(), f"R{h.get('race_no')}" if h.get("race_no") else "", str(h.get("race_name","")).strip()]
    return " · ".join(x for x in bits if x) or "Parsed harness race"

def race_subtitle(h):
    bits=[f"{h.get('distance_m')}m" if h.get("distance_m") else "",h.get("surface",""),h.get("going",""),h.get("prize",""),h.get("date","")]
    return " | ".join(str(x) for x in bits if x)

def parsed_df(rs):
    rows=[]
    for r in rs:
        latest=r.get("recent_runs",[{}])[0] if r.get("recent_runs") else {}
        rows.append({"Tab":r.get("tab"),"Gate":r.get("gate"),"Runner":r.get("horse"),"Scr":r.get("scratched",False),"Odds":r.get("tab_odds"),
                     "Driver":r.get("driver"),"Dri W%":100*r.get("driver_win",0),"Trainer":r.get("trainer"),"Tra W%":100*r.get("trainer_win",0),
                     "Career":r.get("career_rec"),"Course":r.get("course_rec"),"Dist":r.get("distance_rec"),"C&D":r.get("course_distance_rec"),"DLS":r.get("dls"),
                     "OHR":latest.get("ohr",r.get("latest_ohr",0)),"Last Adj":latest.get("mile_rate_adj"),"Last HCP":latest.get("hcp",""),"Form":r.get("form","")})
    return pd.DataFrame(rows)

def prediction_df(res):
    c=res["components"]; rows=[]
    for rank,i in enumerate(res["order"],1):
        r=res["runners"][i]
        rows.append({"Pred":rank,"Tab":r.get("tab"),"Gate":r.get("gate"),"Runner":r.get("horse"),"Market%":100*res["p_mkt"][i],"Fund%":100*res["p_fund"][i],
                     "Win%":100*res["p_win"][i],"Top2%":100*res["top2"][i],"Top3%":100*res["top3"][i],"E[pos]":res["exp_pos"][i],"Fair$":res["fair"][i],
                     "Odds$":r.get("tab_odds"),"EV":res["ev_win"][i],"Conf":res["conf"][i],"Speed Z":c["speed"][i],"Tactics Z":c["tactics"][i],
                     "C&D Z":c["trackdist"][i],"Form Z":c["form"][i],"Conn Z":c["connections"][i],"OHR Z":c["rating"][i],"Sect Z":c["sectionals"][i],
                     "Reliab Z":c["reliability"][i],"Recommendation":res["recs"][i]})
    return pd.DataFrame(rows)

def speed_df(res):
    rows=[]
    for idx in res["early_order"]:
        r=res["runners"][idx]
        rows.append({"Tactical Rank":int(res["early_rank"][idx]),"Gate":r.get("gate"),"Runner":r.get("horse"),"Tactics Score":res["components"]["tactics_raw"][idx],"Win%":100*res["p_win"][idx]})
    return pd.DataFrame(rows)

def csv_bytes(df):
    s=io.StringIO(); df.to_csv(s,index=False); return s.getvalue().encode()

for k,v in (("header",{}),("runners",[]),("warnings",[]),("result",None)): st.session_state.setdefault(k,v)
st.markdown('<div class="hero"><h1 style="margin:0">🏇 HarnessParsePredict</h1><div class="muted">Racing & Sports Enhanced Form parser · harness tactical map + probability model</div></div>',unsafe_allow_html=True)

with st.sidebar:
    st.header("Model settings")
    alpha=st.slider("Market weight α",.25,.90,float(model.MARKET_ALPHA),.01,help="Higher = more market-driven; lower = more harness fundamentals.")
    sims=st.select_slider("Finishing-order simulations",options=[5_000,10_000,20_000,30_000,50_000],value=20_000)
    seed=st.number_input("Random seed",0,999999,42,1)
    st.divider(); st.caption("Harness fundamentals: adjusted mile rate → tactical position/draw → track-distance → recent form → driver/trainer → OHR → sectionals → reliability → freshness.")
    st.caption("Decision support only; race outcomes remain uncertain.")

paste_tab,parsed_tab,map_tab,pred_tab,explain_tab,method_tab=st.tabs(["1 · Paste Data","2 · Parsed Data","3 · Tactical Map","4 · Prediction","5 · Explanations","Method"])
with paste_tab:
    st.subheader("Paste the full Racing & Sports harness Enhanced Form page")
    st.caption("Select all on the Enhanced Form page → copy → paste below. Scratched runners are excluded automatically.")
    pasted=st.text_area("Race data",key="paste_input",height=430,placeholder="Paste harness Enhanced Form text here…",label_visibility="collapsed")
    c1,c2,c3=st.columns([1,1,5])
    with c1: parse_clicked=st.button("Parse race ▶",type="primary",use_container_width=True)
    with c2: st.button("Clear",on_click=reset_app,use_container_width=True)
    if parse_clicked:
        if len(pasted.strip())<300: st.error("The pasted text looks too short. Paste the full Enhanced Form page.")
        else:
            try:
                h,rs,ws=parser.parse(pasted); st.session_state.update(header=h,runners=rs,warnings=ws,result=None); active=[r for r in rs if not r.get("scratched")]
                st.success(f"Parsed {len(rs)} listed runners: {len(active)} active and {len(rs)-len(active)} scratched.") if active else st.error("No active runners were found.")
            except Exception as exc: st.exception(exc)
    if st.session_state["runners"]: st.info(f"Current race: **{race_title(st.session_state['header'])}**")
    if st.session_state["warnings"]:
        with st.expander(f"Parser warnings ({len(st.session_state['warnings'])})"):
            for w in st.session_state["warnings"]: st.warning(w)
with parsed_tab:
    rs,h=st.session_state["runners"],st.session_state["header"]
    if not rs: st.info("Parse a race first.")
    else:
        st.subheader(race_title(h)); st.caption(race_subtitle(h)); df=parsed_df(rs)
        st.dataframe(df,use_container_width=True,hide_index=True,height=520,column_config={"Dri W%":st.column_config.NumberColumn(format="%.1f%%"),"Tra W%":st.column_config.NumberColumn(format="%.1f%%"),"Odds":st.column_config.NumberColumn(format="$%.2f")})
        st.download_button("Download parsed data (CSV)",data=csv_bytes(df),file_name="harness_parsed.csv",mime="text/csv")
with map_tab:
    rs,h=st.session_state["runners"],st.session_state["header"]
    if not rs: st.info("Parse a race first.")
    else:
        if st.button("Build tactical map ▶",type="primary"):
            try: st.session_state["result"]=model.predict(rs,h,alpha=float(alpha),sims=int(sims),seed=int(seed))
            except Exception as exc: st.exception(exc)
        res=st.session_state["result"]
        if res:
            df=speed_df(res); leader=df.iloc[0]; st.markdown(f"### Projected early/tactical leader: **Gate {leader['Gate']} · {leader['Runner']}**")
            st.dataframe(df,use_container_width=True,hide_index=True,column_config={"Win%":st.column_config.NumberColumn(format="%.1f%%"),"Tactics Score":st.column_config.NumberColumn(format="%.3f")})
            st.caption("Current Gate uses the listed field/start order where the pasted page does not expose a separate current HCP/barrier. Recent Fr/Sr draws and in-running positions drive most of the tactical score.")
with pred_tab:
    rs,h=st.session_state["runners"],st.session_state["header"]
    if not rs: st.info("Parse a race first.")
    else:
        st.subheader(race_title(h)); st.caption(race_subtitle(h))
        if st.button("Predict race ▶",type="primary",key="predict"):
            try:
                with st.spinner("Running harness ensemble and finishing-order simulation…"): st.session_state["result"]=model.predict(rs,h,alpha=float(alpha),sims=int(sims),seed=int(seed))
            except Exception as exc: st.exception(exc)
        res=st.session_state["result"]
        if res:
            df=prediction_df(res); w=df.iloc[0]
            st.markdown(f'<div class="pick"><div class="muted">MODEL TOP PICK</div><h2 style="margin:.1rem 0">#{int(w["Tab"])} {w["Runner"]}</h2><b>Win {w["Win%"]:.1f}%</b> · Top 3 {w["Top3%"]:.1f}% · Fair ${w["Fair$"]:.2f} · EV {w["EV"]:+.2f} · Confidence {int(w["Conf"])}/9</div>',unsafe_allow_html=True)
            m1,m2,m3,m4=st.columns(4); m1.metric("Overall confidence",f"{res['overall_conf']}/9"); m2.metric("Market weight",f"{alpha:.2f}"); m3.metric("Projected leader",res["runners"][res["early_order"][0]]["horse"]); m4.metric("Active field",str(len(res["runners"])))
            st.dataframe(df,use_container_width=True,hide_index=True,height=540,column_config={"Market%":st.column_config.NumberColumn(format="%.1f%%"),"Fund%":st.column_config.NumberColumn(format="%.1f%%"),"Win%":st.column_config.ProgressColumn(format="%.1f%%",min_value=0,max_value=100),"Top2%":st.column_config.NumberColumn(format="%.1f%%"),"Top3%":st.column_config.NumberColumn(format="%.1f%%"),"E[pos]":st.column_config.NumberColumn(format="%.2f"),"Fair$":st.column_config.NumberColumn(format="$%.2f"),"Odds$":st.column_config.NumberColumn(format="$%.2f"),"EV":st.column_config.NumberColumn(format="%+.2f")})
            st.download_button("Download prediction (CSV)",data=csv_bytes(df),file_name="harness_prediction.csv",mime="text/csv")
with explain_tab:
    res=st.session_state["result"]
    if not res: st.info("Run the prediction first.")
    else:
        st.subheader(f"Runner explanations · confidence {res['overall_conf']}/9")
        for rank,i in enumerate(res["order"],1):
            r=res["runners"][i]
            with st.expander(f"{rank}. #{r.get('tab')} {r.get('horse')} — Win {res['p_win'][i]*100:.1f}% · {res['recs'][i]}",expanded=rank<=3):
                st.markdown(f"**{res['recs'][i]}**"); st.write(res["why"][i]); c=res["components"]
                st.dataframe(pd.DataFrame([{"Speed Z":c["speed"][i],"Tactics Z":c["tactics"][i],"Track/Dist Z":c["trackdist"][i],"Form Z":c["form"][i],"Connections Z":c["connections"][i],"OHR Z":c["rating"][i],"Sectionals Z":c["sectionals"][i],"Reliability Z":c["reliability"][i]}]),hide_index=True,use_container_width=True)
with method_tab:
    st.subheader("How the harness model works")
    st.markdown("""
1. **Field parser** — extracts race conditions, runners, prices, scratches, drivers and trainers.
2. **Adjusted mile-rate speed** — recency-weights R&S **Race Mile Rate Adj** and IMR figures, with extra relevance for the same track and similar distance.
3. **Tactical map** — estimates likely early/settling position from recent 1200 m / 800 m / bell-lap positions and prior **Fr/Sr** starting positions, with only a mild current gate prior.
4. **Track & distance** — combines Course, Distance and Course & Distance records with shrinkage for small samples.
5. **Recent form** — finishing position and margins over the most recent starts.
6. **Connections** — driver and trainer Last50 strike rates plus Driver/Horse and Driver/Trainer combinations when supplied.
7. **Rating and sectionals** — recent OHR plus L800/L400 closing figures.
8. **Reliability** — penalizes recurring galloping/breaking/rough-racing notes and gives a small compensation to runs where the horse was held up or not fully tested.
9. **Market blend** — de-vigged listed odds are blended with the fundamental probability. Sidebar α controls market influence.
10. **Finishing-order simulation** — Plackett–Luce simulations produce Top-2, Top-3 and expected finishing position, followed by fair odds and EV.

**V1 limitation:** if the pasted field does not expose a separate current barrier/HCP, the app uses listed runner order as the current gate proxy. A historical training dataset would allow these component weights and track-specific draw effects to be calibrated rather than hand-set.
""")
