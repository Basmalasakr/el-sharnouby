import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from theme import header, kpi, insight, plot

try:
    from notifier import send_alert
except ImportError:
    send_alert = None

DATA = "data/"
CH = {"LOC001": "Retail", "LOC002": "Online", "LOC003": "Wholesale"}
OVERSTOCK_DOC = 180

st.set_page_config(layout="wide", page_title="Smart Inventory", page_icon="")
header("Smart Inventory & Replenishment", "What should move, where, and when?", "APP 02")

@st.cache_data(show_spinner=False)
def get_sales():
    cols = ["Order_Date", "Location_ID", "Product_ID", "Product_Name", "Quantity", "Net_Sales_EGP", "Estimated_COGS_EGP", "Gross_Profit_EGP"]
    try:
        s = pd.read_csv(DATA + "Sales_Transactions.csv", usecols=cols, parse_dates=["Order_Date"])
    except:
        try:
            s = pd.read_parquet(DATA + "Sales_Transactions.parquet", columns=cols)
            s['Order_Date'] = pd.to_datetime(s['Order_Date'])
        except:
            st.error("Sales data missing! Please add Sales_Transactions.parquet or .csv")
            st.stop()
            
    s["Channel"] = s["Location_ID"].map(CH).fillna(s["Location_ID"])
    s["Month"] = s.Order_Date.dt.to_period("M").dt.to_timestamp()
    return s

@st.cache_data(show_spinner=False)
def load_inv():
    try:
        inv = pd.read_csv(DATA + "Inventory_History.csv", parse_dates=["Snapshot_Month"])
    except:
        try:
            inv = pd.read_parquet(DATA + "Inventory_History.parquet")
            inv['Snapshot_Month'] = pd.to_datetime(inv['Snapshot_Month'])
        except:
            st.error("Inventory data missing! Please add Inventory_History.parquet or .csv")
            st.stop()
            
    inv["Channel"] = inv.get("Location_ID", inv.get("Location_Name")).map(CH).fillna(inv.get("Location_ID", inv.get("Location_Name")))
    
    s = get_sales()
    cost = s.groupby("Product_ID")["Estimated_COGS_EGP"].sum() / s.groupby("Product_ID")["Quantity"].sum().replace(0, 1)
    inv["Unit_Cost"] = inv.Product_ID.map(cost).fillna(100)
    inv["Stock_Value"] = inv.Closing_Stock * inv["Unit_Cost"]
    
    cut = (s.Order_Date.max().to_period("M") - 11).to_timestamp()
    p = s[s.Order_Date >= cut].groupby(["Product_ID", "Channel"]).agg(
        q=("Quantity", "sum"), n=("Net_Sales_EGP", "sum"), g=("Gross_Profit_EGP", "sum"))
    
    p["Net_Unit"] = p.n / p.q.replace(0, np.nan)
    p["GP_Unit"] = p.g / p.q.replace(0, np.nan)
    inv = inv.merge(p[["Net_Unit", "GP_Unit"]], on=["Product_ID", "Channel"], how="left")
    
    if "Stockout_Days_In_Month" in inv.columns and "Avg_Daily_Sales_90D" in inv.columns:
        daily_loss = inv["Stockout_Days_In_Month"] * inv["Avg_Daily_Sales_90D"]
    else:
        daily_loss = 0
        
    inv["Lost_Net"] = daily_loss * inv["Net_Unit"].fillna(0)
    inv["Lost_GP"] = daily_loss * inv["GP_Unit"].fillna(0)
    
    inv["Status"] = np.select(
        [inv.Closing_Stock <= 0, inv.Closing_Stock <= inv.get("Reorder_Point_Units", 0), inv.get("Days_of_Cover", 0) > OVERSTOCK_DOC],
        ["Stockout", "Below ROP", "Overstock"], "Healthy")
    return inv, cut

@st.cache_data(show_spinner=False)
def portfolio():
    inv, cut = load_inv(); s = get_sales()
    names = s.drop_duplicates("Product_ID").set_index("Product_ID")["Product_Name"]
    val = s[s.Order_Date >= cut].groupby("Product_ID")["Net_Sales_EGP"].sum().sort_values(ascending=False)
    cum = val.cumsum() / val.sum()
    abc = pd.cut(cum, [0, .8, .95, 1.0001], labels=list("ABC")).astype(str)
    
    mo = s.groupby(["Product_ID", "Month"])["Quantity"].sum().unstack(fill_value=0)
    cv = (mo.std(axis=1) / mo.mean(axis=1).replace(0, np.nan)).reindex(val.index).fillna(0)
    xyz = pd.qcut(cv.rank(method="first"), 3, labels=["X", "Y", "Z"]).astype(str)
    
    pf = pd.DataFrame({"Name": names.reindex(val.index), "Net_Sales_12m": val, "ABC": abc, "CV": cv, "XYZ": xyz})
    
    y = inv[inv.Snapshot_Month >= cut]
    
    if "Sold_Qty" in y.columns:
        sold = y.groupby("Channel")["Sold_Qty"].sum()
    else:
        sold = y.groupby("Channel")["Closing_Stock"].sum() * 0
        
    avg_inv = y.groupby(["Channel", "Snapshot_Month"])["Closing_Stock"].sum().groupby("Channel").mean()
    cur = inv[inv.Snapshot_Month == inv.Snapshot_Month.max()]
    
    loc = pd.DataFrame({"Sold_12m": sold, "Avg_Stock": avg_inv})
    loc["Turns"] = loc.Sold_12m / loc.Avg_Stock.replace(0, np.nan)
    loc["Days_of_Cover_Avg"] = 365 / loc.Turns.replace(0, np.nan)
    
    if "Avg_Daily_Sales_90D" in cur.columns:
        dem = cur.groupby("Channel")["Avg_Daily_Sales_90D"].sum()
    else:
        dem = pd.Series(1, index=cur["Channel"].unique())
    loc["Cover_Now"] = cur.groupby("Channel")["Closing_Stock"].sum() / dem.replace(0, np.nan)
    
    if "Sold_Qty" in y.columns:
        pl = y.groupby(["Product_ID", "Channel"]).agg(sold=("Sold_Qty", "sum"), stock=("Closing_Stock", "mean")).reset_index()
    else:
        pl = y.groupby(["Product_ID", "Channel"]).agg(sold=("Closing_Stock", "sum"), stock=("Closing_Stock", "mean")).reset_index()
        pl['sold'] = 0
        
    pl["Turns"] = pl.sold / pl.stock.replace(0, np.nan)
    return pf, loc, pl

@st.cache_data(show_spinner=False)
def generate_forecasts():
    inv, _ = load_inv()
    days = inv.Snapshot_Month.dt.days_in_month
    avail = (days - inv.get("Stockout_Days_In_Month", 0)).clip(lower=days * 0.5)
    inv["Demand"] = inv.get("Sold_Qty", 0) * days / avail
    wide = inv.pivot_table(index=["Channel", "Product_ID"], columns="Snapshot_Month", values="Demand").sort_index(axis=1).fillna(0)
    
    H = 3; out = []
    for key, h in zip(wide.index, wide.values):
        ma3 = np.repeat(h[-3:].mean(), H) if len(h) >= 3 else np.zeros(H)
        sn = np.array([h[len(h) - 12 + i] for i in range(H)]) if len(h) >= 12 else ma3
        blend = 0.5 * ma3 + 0.5 * sn
        out.append((key, "Blend", *blend))
        
    fc = pd.DataFrame(out, columns=["Key", "Model", "M1", "M2", "M3"]).set_index("Key").reset_index()
    fc[["Channel", "Product_ID"]] = pd.DataFrame(fc.Key.tolist(), index=fc.index)
    fc["Forecast_30d"] = fc.M1; fc["Forecast_60d"] = fc.M1 + fc.M2; fc["Forecast_90d"] = fc.M1 + fc.M2 + fc.M3
    return fc, wide

@st.cache_data(show_spinner=False)
def plan(surge=0, lt_buffer=0, review=30):
    inv, _ = load_inv(); fc, _ = generate_forecasts()
    cur = inv[inv.Snapshot_Month == inv.Snapshot_Month.max()].merge(
        fc[["Channel", "Product_ID", "Forecast_30d", "Forecast_60d", "Forecast_90d"]], on=["Channel", "Product_ID"], how="left")
    
    d = (cur.Forecast_90d / 90).fillna(0) * (1 + surge / 100)
    lt = cur.get("Supplier_Lead_Time_Days", 7) + lt_buffer
    cur["Order_Qty"] = np.ceil((d * (lt + review) + cur.get("Safety_Stock_Units", 0) - cur.Closing_Stock).clip(lower=0))
    cur["Order_Value"] = cur.Order_Qty * cur.Unit_Cost
    cur["Excess"] = np.floor((cur.Closing_Stock - d * OVERSTOCK_DOC).clip(lower=0))
    cur["Action"] = np.select([cur.Closing_Stock <= 0, cur.Order_Qty > 0, cur.Excess > 0], ["1-Urgent order", "2-Order", "3-Overstock"], "4-OK")
    cur["Factory_Link"] = "-"
    
    need_ = cur[cur.Order_Qty > 0][["Product_ID", "Product_Name", "Channel", "Order_Qty", "Unit_Cost"]].rename(columns={"Channel": "To", "Order_Qty": "Need"})
    give = cur[cur.Excess > 0][["Product_ID", "Channel", "Excess"]].rename(columns={"Channel": "From"})
    tr = need_.merge(give, on="Product_ID"); tr = tr[tr.From != tr.To].copy()
    tr["Qty"] = np.minimum(tr.Need, tr.Excess); tr["Value"] = tr.Qty * tr.Unit_Cost
    return cur, tr.sort_values("Value", ascending=False)

inv, cut = load_inv()
months = sorted(inv.Snapshot_Month.unique(), reverse=True)

with st.container(border=True):
    st.markdown("**Action Simulator & Filters**")
    c1, c2, c3, c4 = st.columns(4)
    sel = c1.selectbox("Diagnosis month", months, format_func=lambda x: pd.Timestamp(x).strftime("%b %Y"))
    surge = c2.slider("Demand Surge (%)", -20, 50, 0, 5)
    buf = c3.slider("Lead Time Delay (days)", 0, 30, 0, 1)
    review = c4.slider("Review cycle (days)", 7, 60, 30, 1)

t1, t2, t3, t4 = st.tabs(["1. Health & Financial Leakage", "2. Intelligence (ABC/XYZ)", "3. Action Plan & Transfers", "4. AI Demand Forecasting"])

with t1:
    cur = inv[inv.Snapshot_Month == sel]; y12 = inv[inv.Snapshot_Month >= cut]
    cnt = cur.Status.value_counts(); score = (cur.Status == "Healthy").mean() * 100
    ov_val = cur[cur.Status == "Overstock"].Stock_Value.sum()
    
    r1 = st.columns(6)
    r1[0].markdown(kpi("Inventory Health", f"{score:.0f}/100", "% SKU-locations healthy", "Normal" if score >= 80 else "Critical", "ok" if score >= 80 else "bad"), unsafe_allow_html=True)
    r1[1].markdown(kpi("Stockouts", f"{cnt.get('Stockout', 0)}", f"of {len(cur)} Locations"), unsafe_allow_html=True)
    r1[2].markdown(kpi("Below ROP", f"{cnt.get('Below ROP', 0)}", "Stock <= ROP"), unsafe_allow_html=True)
    r1[3].markdown(kpi("Overstock", f"{cnt.get('Overstock', 0)}", f"Cover > {OVERSTOCK_DOC} days"), unsafe_allow_html=True)
    r1[4].markdown(kpi("Stock Value", f"{cur.Stock_Value.sum()/1e6:,.1f}M", "EGP, at est. cost"), unsafe_allow_html=True)
    r1[5].markdown(kpi("Cash in Overstock", f"{ov_val/1e6:,.1f}M", f"{ov_val/cur.Stock_Value.sum() if cur.Stock_Value.sum()>0 else 0:.0%} of Total"), unsafe_allow_html=True)
    
    st.write(""); r2 = st.columns(3)
    r2[0].markdown(kpi("Lost Net Sales (12m)", f"{y12.Lost_Net.sum()/1e6:,.2f}M EGP", "Financial Leakage"), unsafe_allow_html=True)
    r2[1].markdown(kpi("Lost Gross Profit (12m)", f"{y12.Lost_GP.sum()/1e6:,.2f}M EGP", "Profit Leakage"), unsafe_allow_html=True)
    r2[2].markdown(kpi("Stockout Days (12m)", f"{int(y12.get('Stockout_Days_In_Month', pd.Series([0])).sum()):,}", "SKU-location days"), unsafe_allow_html=True)
    
    short = cur[cur.Status.isin(["Stockout", "Below ROP"])]
    w_share = (short.Channel.str.contains("Wholesale")).mean() if len(short) else 0
    ro_val = cur[(cur.Status == "Overstock") & (~cur.Channel.str.contains("Wholesale"))].Stock_Value.sum()
    st.write("")
    insight(f"**{w_share:.0%}** of short SKU-locations are in **Wholesale**, while Retail + Online hold "
            f"**{ro_val/ov_val if ov_val else 0:.0%}** of the overstock cash. Stock is in the wrong place, not only in the wrong quantity.")

    a, b = st.columns([1.15, 1])
    with a, st.container(border=True):
        st.markdown("**Status by location**")
        ct = pd.crosstab(cur.Channel, cur.Status).reindex(columns=["Healthy", "Below ROP", "Stockout", "Overstock"], fill_value=0)
        st.dataframe(ct, use_container_width=True)
    with b, st.container(border=True):
        st.markdown("**Top 5 Overstock by Cash Tied**")
        t = cur[cur.Status == "Overstock"].sort_values("Stock_Value", ascending=False).head(5)
        st.dataframe(t[['Product_ID', 'Channel', 'Closing_Stock', 'Stock_Value']], use_container_width=True, hide_index=True)

with t2:
    pf, loc, pl = portfolio()
    st.markdown("**ABC (Value) × XYZ (Volatility) Intelligence Matrix**")
    mat = pd.crosstab(pf.ABC, pf.XYZ).reindex(index=list("ABC"), columns=list("XYZ"), fill_value=0)
    
    a, b = st.columns([1, 1.2])
    with a, st.container(border=True):
        fig = go.Figure(go.Heatmap(z=mat.values, x=["X (Stable)", "Y (Variable)", "Z (Volatile)"], y=["A (High)", "B (Medium)", "C (Low)"],
                                   text=mat.values, texttemplate="%{text} SKUs", colorscale="Blues", showscale=False))
        fig.update_yaxes(autorange="reversed"); plot(fig, 300)
    with b, st.container(border=True):
        st.markdown("**Critical Items: Class A & Z (High Value, Volatile Demand)**")
        az = pf[(pf.ABC == "A") & (pf.XYZ == "Z")]
        st.dataframe(az[['Name', 'Net_Sales_12m', 'CV']].head(8), use_container_width=True, hide_index=True)

with t3:
    base, _ = plan(0, 0, review); sc, tr = plan(surge, buf, review)
    ns = sc.Action.value_counts()
    
    k = st.columns(4)
    k[0].markdown(kpi("Urgent orders", f"{ns.get('1-Urgent order', 0)}", "Requires immediate factory action", "info"), unsafe_allow_html=True)
    k[1].markdown(kpi("Order units", f"{sc.Order_Qty.sum():,.0f}", "Total units to replenish"), unsafe_allow_html=True)
    k[2].markdown(kpi("Order value", f"{sc.Order_Value.sum()/1e6:,.1f}M EGP", "Capital required for orders"), unsafe_allow_html=True)
    k[3].markdown(kpi("Transfer candidates", f"{len(tr)}", f"Saves {tr.Value.sum()/1e6:,.2f}M EGP via logistics"), unsafe_allow_html=True)
    
    st.write("")
    insight(f"Internal logistics (Transfers) can safely cover **{tr.Qty.sum()/max(sc.Order_Qty.sum(), 1):.0%}** of the required order units, directly reducing the {sc.Order_Value.sum()/1e6:,.1f}M EGP capital requirement.")
    
    with st.container(border=True):
        st.markdown("**Smart Inter-Branch Transfers (Overstock to Stockout)**")
        if not tr.empty:
            st.dataframe(tr[['Product_ID', 'From', 'To', 'Qty', 'Value']].head(10), use_container_width=True, hide_index=True)
            if send_alert and st.button("Send Top Transfer to CEO for Approval"):
                top_transfer = tr.iloc[0]
                msg = (
                    f"Inventory Transfer Request\n\n"
                    f"Product: {top_transfer['Product_ID']}\n"
                    f"From: {top_transfer['From']} -> To: {top_transfer['To']}\n"
                    f"Qty: {top_transfer['Qty']} Units\n"
                    f"Saved Capital: {top_transfer['Value']:,.0f} EGP\n\n"
                    f"Approve this transfer?"
                )
                send_alert(msg)
                st.toast("Transfer request sent to Telegram!")
        else:
            st.info("No viable transfers found.")

with t4:
    with st.container(border=True):
        st.markdown("**AI Demand Forecast (Next 30/60/90 Days)**")
        
        ext = DATA + "Forecast_Results.csv"
        if os.path.exists(ext):
            e = pd.read_csv(ext)
            
            if 'WAPE_Error' in e.columns:
                if e['Forecast_60d'].sum() < e['Forecast_30d'].sum() * 1.5:  
                    e['Cum_60d'] = e['Forecast_30d'] + e['Forecast_60d']
                    e['Cum_90d'] = e['Cum_60d'] + e['Forecast_90d']
                else:
                    e['Cum_60d'] = e['Forecast_60d']
                    e['Cum_90d'] = e['Forecast_90d']
                
                display_cols = ['Product_ID', 'Forecast_30d', 'Cum_60d', 'Cum_90d']
                e_display = e[[c for c in display_cols if c in e.columns]].copy()
                st.dataframe(e_display.head(15), use_container_width=True, hide_index=True)
        else:
            st.info("Pending ML model output... Please place 'Forecast_Results.csv' in the data folder.")
