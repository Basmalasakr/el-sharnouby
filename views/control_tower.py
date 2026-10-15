import os
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from theme import header, kpi, pill, insight, plot, PRIMARY, PALETTE

try:
    from notifier import send_alert
except ImportError:
    send_alert = None

try:
    from ai_layer import get_ai_insights
except ImportError:
    try:
        from views.ai_layer import get_ai_insights
    except ImportError:
        get_ai_insights = None

DATA = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")

st.set_page_config(layout="wide", page_title="Control Tower")

if 'decision_log' not in st.session_state:
    st.session_state.decision_log = []

@st.cache_data(show_spinner=False)
def load():
    c = ["Order_Date", "Channel", "Product_ID", "Product_Family", "Quantity", "Discount_Pct", "Gross_Sales_EGP",
         "Net_Sales_EGP", "Estimated_COGS_EGP", "Gross_Profit_EGP", "Returned", "Refund_Value_EGP", "Customer_ID", "Customer_Governorate"]
    try:
        s = pd.read_csv(DATA / "Sales_Transactions.csv", usecols=c, parse_dates=["Order_Date"])
    except:
        s = pd.read_parquet(DATA / "Sales_Transactions.parquet", columns=c)
        s['Order_Date'] = pd.to_datetime(s['Order_Date'])
    return s

@st.cache_data(show_spinner=False)
def load_context_data():
    try: qc = pd.read_csv(DATA / "Quality.csv")
    except: qc = pd.DataFrame()
    try: md = pd.read_csv(DATA / "Machine_Downtime.csv")
    except: md = pd.DataFrame()
    try: inv = pd.read_csv(DATA / "Inventory_History.csv")
    except: inv = pd.DataFrame()
    try: po = pd.read_csv(DATA / "Purchase_Orders.csv")
    except: po = pd.DataFrame()
    return qc, md, inv, po

s = load()
qc, md, inv, po = load_context_data()

header("Executive Command Center", "If the CEO had one screen, what should it know?", "APP 01")

allch = sorted(s.Channel.unique())
chs = st.multiselect("Filter by Channel:", allch, default=allch)
d = s[s.Channel.isin(chs)]
if d.empty:
    st.warning("Select at least one channel.")
    st.stop()

main_t1, main_t2 = st.tabs(["1. Executive Dashboard (Analytics)", "2. Omnichannel AI Copilot (God Mode)"])

with main_t1:
    net, gp = d.Net_Sales_EGP.sum(), d.Gross_Profit_EGP.sum()
    margin = gp / net if net > 0 else 0
    m = d.Order_Date.dt.month
    ytd = d[m <= 9].groupby(d.Order_Date.dt.year[m <= 9]).Net_Sales_EGP.sum()
    yoy = ytd.pct_change().iloc[-1] if len(ytd) > 1 else np.nan
    mon = d.groupby(d.Order_Date.dt.to_period("M").dt.to_timestamp()).Net_Sales_EGP.sum()
    mom = mon.iloc[-1] / mon.iloc[-2] - 1 if len(mon) > 1 else 0
    pm = d.groupby("Product_ID").agg(net=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum"))
    pm["m"] = pm.gp / pm.net
    low = pm[pm.m < 0.05]

    r1 = st.columns(5)
    r1[0].markdown(kpi("Net Sales", f"{net/1e6:,.1f}M", "EGP, Oct-23 - Sep-26"), unsafe_allow_html=True)
    r1[1].markdown(kpi("Gross Profit", f"{gp/1e6:,.1f}M", "EGP"), unsafe_allow_html=True)
    r1[2].markdown(kpi("Gross Margin", f"{margin:.1%}", "gross profit / net sales", "Low" if margin < .20 else "Healthy", "bad" if margin < .20 else "ok"), unsafe_allow_html=True)
    r1[3].markdown(kpi("Weighted Discount", f"{1 - net/d.Gross_Sales_EGP.sum():.1%}", "1 - net / gross"), unsafe_allow_html=True)
    r1[4].markdown(kpi("Units Sold", f"{d.Quantity.sum()/1e6:,.2f}M", "all channels selected"), unsafe_allow_html=True)
    st.write("")
    r2 = st.columns(5)
    r2[0].markdown(kpi("YoY (Jan-Sep)", f"{yoy:+.1%}" if pd.notna(yoy) else "N/A", f"{ytd.index[-1]} vs {ytd.index[-2]}, like-for-like" if len(ytd) > 1 else ""), unsafe_allow_html=True)
    r2[1].markdown(kpi("MoM", f"{mom:+.1%}", f"{mon.index[-1]:%b} vs {mon.index[-2]:%b} seasonal" if len(mon) > 1 else ""), unsafe_allow_html=True)
    r2[2].markdown(kpi("Return Rate", f"{(d.Returned == 'Yes').mean():.1%}", "of order lines"), unsafe_allow_html=True)
    r2[3].markdown(kpi("Refunds", f"{d.Refund_Value_EGP.sum()/1e6:,.2f}M", "EGP"), unsafe_allow_html=True)
    r2[4].markdown(kpi("Low-margin SKUs", f"{len(low)}", "products below 5% margin", "Review" if len(low) else "None", "warn" if len(low) else "ok"), unsafe_allow_html=True)

    g = d.groupby("Channel").agg(net=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum"), gs=("Gross_Sales_EGP", "sum"), cogs=("Estimated_COGS_EGP", "sum"))
    g["share"] = g.net / g.net.sum() if g.net.sum() > 0 else 0
    g["m"] = g.gp / g.net
    if not g.empty:
        top = g.net.idxmax()
        st.write("")
        insight(f"<b>{top}</b> brings {g.share[top]:.0%} of sales at only {g.m[top]:.1%} margin, vs {g.m.max():.0%} in the best channel. Growth slowed from +9.3% (2025) to {yoy:+.1%} (2026) while margin stayed flat - growth is not converting into profit.")

    a, b = st.columns([1, 1.4])
    with a, st.container(border=True):
        st.markdown("**Channel performance**")
        rows = "".join(f"<tr><td>{c}</td><td>{r.net/1e6:,.1f}M</td><td>{r.share:.0%}</td><td>{pill(f'{r.m:.1%}', 'bad' if r.m < .2 else 'ok')}</td></tr>" for c, r in g.iterrows())
        st.markdown(f'<table class="tbl"><tr><th>CHANNEL</th><th>NET SALES</th><th>SHARE</th><th>MARGIN</th></tr>{rows}</table>', unsafe_allow_html=True)
    with b, st.container(border=True):
        st.markdown("**Monthly net sales**")
        ms = mon.reset_index()
        fig = px.line(ms, x="Order_Date", y="Net_Sales_EGP", color_discrete_sequence=[PRIMARY])
        fig.update_yaxes(rangemode="tozero")
        plot(fig, 250)

    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**Seasonality index** (1.0 = average month)")
        mm = d.groupby([d.Order_Date.dt.year, d.Order_Date.dt.month]).Net_Sales_EGP.sum()
        si = mm.groupby(level=1).mean()
        si = (si / si.mean()).reset_index()
        si.columns = ["Month", "Index"]
        si["Month"] = si.Month.map(lambda x: pd.Timestamp(2000, x, 1).strftime("%b"))
        fig = px.bar(si, x="Month", y="Index", color_discrete_sequence=[PRIMARY])
        plot(fig, 250)
        st.caption("Averaged over available years; growth trend slightly inflates later months.")
    with c2, st.container(border=True):
        st.markdown("**Product family contribution**")
        f = d.groupby("Product_Family").agg(net=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum")).sort_values("net", ascending=False)
        dn = px.pie(f.reset_index(), values="net", names="Product_Family", hole=0.62, color_discrete_sequence=PALETTE)
        dn.update_traces(textinfo="percent", sort=False)
        dn.update_layout(legend=dict(orientation="h", y=-0.05))
        plot(dn, 210, legend=True)
        rows = "".join(f"<tr><td>{n}</td><td>{r.net/1e6:,.1f}M</td><td>{r.net/net:.0%}</td><td>{pill(f'{r.gp/r.net:.1%}', 'bad' if r.gp/r.net < .2 else 'ok')}</td></tr>" for n, r in f.iterrows())
        st.markdown(f'<table class="tbl"><tr><th>FAMILY</th><th>NET SALES</th><th>SHARE</th><th>MARGIN</th></tr>{rows}</table>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("**Discount impact on margin**")
        bands = pd.cut(d.Discount_Pct, [-0.001, 0, 0.10, 0.20, 0.30, 0.60], labels=["0%", "0-10%", "10-20%", "20-30%", ">30%"])
        db = d.groupby(bands, observed=True).agg(net=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum"))
        db["Margin"] = db.gp / db.net
        db = db.reset_index().rename(columns={"Discount_Pct": "Discount band"})
        x1, x2 = st.columns([1.2, 1])
        with x1:
            fig = px.bar(db, x="Discount band", y="Margin", color_discrete_sequence=[PRIMARY])
            fig.update_yaxes(tickformat=".0%")
            plot(fig, 230)
        with x2:
            st.dataframe(db.assign(**{"Net Sales (M)": (db.net / 1e6).map("{:,.1f}".format), "Margin": (db.Margin * 100).map("{:.1f}".format)})[["Discount band", "Net Sales (M)", "Margin"]].rename(columns={"Margin": "Margin %"}), hide_index=True, width="stretch")

    g1, g2 = st.columns(2)
    with g1, st.container(border=True):
        st.markdown("**Net sales by customer governorate**")
        gv = d.groupby("Customer_Governorate").Net_Sales_EGP.sum().sort_values().div(1e6).reset_index()
        fig = px.bar(gv, x="Net_Sales_EGP", y="Customer_Governorate", orientation="h", color_discrete_sequence=[PRIMARY])
        fig.update_xaxes(ticksuffix="M")
        plot(fig, 360)
    with g2, st.container(border=True):
        st.markdown("**Top 10 customers**")
        cu = d.groupby("Customer_ID").agg(net=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum")).sort_values("net", ascending=False)
        t10 = cu.head(10)
        rows = "".join(f"<tr><td>{i}</td><td>{r.net/1e6:,.2f}M</td><td>{r.net/net:.2%}</td><td>{pill(f'{r.gp/r.net:.1%}', 'bad' if r.gp/r.net < .2 else 'ok')}</td></tr>" for i, r in t10.iterrows())
        st.markdown(f'<table class="tbl"><tr><th>CUSTOMER</th><th>NET SALES</th><th>SHARE</th><th>MARGIN</th></tr>{rows}</table>', unsafe_allow_html=True)
        n10 = len(cu) // 10
        st.caption(f"Top 10 customers = {t10.net.sum()/net:.1%} of sales; the top 10% of customers ({n10:,}) = {cu.net.head(n10).sum()/net:.0%}.")

with main_t2:
    if get_ai_insights is None:
        st.error("Error: The file ai_layer.py was not found.")
        st.stop()

    worst_margins = pm[pm['net'] > 0].sort_values('m').head(3).index.tolist() if not pm.empty else []
    top_returns = d[d.get('Returned', '') == 'Yes']['Product_ID'].value_counts().head(2).index.tolist() if 'Returned' in d.columns else []
    price_leakage = (d[d.get('Discount_Pct', 0) > 0.15]['Gross_Sales_EGP'] * d[d.get('Discount_Pct', 0) > 0.15]['Discount_Pct']).sum() if 'Discount_Pct' in d.columns else 0
    top_defects = qc['Root_Cause'].value_counts().head(2).index.tolist() if not qc.empty and 'Root_Cause' in qc.columns else []
    top_downtime = md[md.get('Planned', 'No').astype(str).str.lower() == 'no']['Reason'].value_counts().head(2).index.tolist() if not md.empty and 'Reason' in md.columns else []

    overstock_items, stockout_items = [], []
    if not inv.empty and 'Days_of_Cover' in inv.columns and 'Product_ID' in inv.columns:
        latest_inv = inv[inv['Snapshot_Month'] == inv['Snapshot_Month'].max()] if 'Snapshot_Month' in inv.columns else inv
        overstock_items = latest_inv[latest_inv['Days_of_Cover'] > 180]['Product_ID'].head(2).tolist()
        stockout_items = latest_inv[latest_inv['Closing_Stock'] <= 0]['Product_ID'].head(2).tolist()

    late_suppliers = po[po['Delay_Days'] > 7]['Supplier_ID'].value_counts().head(2).index.tolist() if not po.empty and 'Delay_Days' in po.columns else []

    st.markdown("### Executive Operations Room")
    user_query = st.text_input("Ask the Executive Board (Cross-functional Query):", placeholder="Ask about specific products or KPIs currently in the data context.")

    if st.button("Consult AI Agents & Record Decision", type="primary"):
        if not user_query:
            st.warning("Please enter a question.")
        else:
            with st.spinner("AI is processing..."):
                context = f"""
                -- Sales & Financials --
                Loss due to High Discounts: {price_leakage} EGP
                Products with Worst Margins (IDs): {worst_margins}
                Highly Returned Products (IDs): {top_returns}
                
                -- Factory & Quality --
                Top Quality Defects Causes: {top_defects}
                Top Machine Downtime Causes: {top_downtime}
                
                -- Inventory & Warehousing --
                Products with Overstock (>180 days, IDs): {overstock_items}
                Products with Stockouts (0 units, IDs): {stockout_items}
                
                -- Procurement & Suppliers --
                Suppliers with critical delays (>7 days, IDs): {late_suppliers}
                """
                
                agents_data = get_ai_insights(context_data=context, user_query=user_query, role_type="Executive Board")
                
                if isinstance(agents_data, dict) and "error" not in agents_data:
                    ag1, ag2, ag3 = st.columns(3)
                    with ag1, st.container(border=True):
                        st.markdown("**Sales Director (AI)**")
                        st.info(agents_data.get("sales_agent_response", ""))
                    with ag2, st.container(border=True):
                        st.markdown("**Operations Director (AI)**")
                        st.warning(agents_data.get("operations_agent_response", ""))
                    with ag3, st.container(border=True):
                        st.markdown("**Chief Financial Officer (AI Decision)**")
                        st.success(agents_data.get("finance_agent_decision", ""))
                        
                    st.session_state.decision_log.append({
                        "Date & Time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                        "Business Query": user_query,
                        "Approved Decision (Closed Loop)": agents_data.get("finance_agent_decision", "")
                    })
                    
                    if send_alert:
                        msg = f"Control Tower AI Insight\n\nQuery: {user_query}\nDecision: {agents_data.get('finance_agent_decision', '')}\n\nAction: Implement this strategy?"
                        send_alert(msg)
                        st.toast("AI Strategy forwarded to Executive via Telegram!")
                else:
                    st.error("AI Error: " + agents_data.get("error", "Unknown Error"))

    st.markdown("---")
    st.markdown("### Omnichannel Decision Log")

    if len(st.session_state.decision_log) > 0:
        st.dataframe(pd.DataFrame(st.session_state.decision_log), use_container_width=True, hide_index=True)
    else:
        st.caption("Submit a query to record the first strategic decision.")
