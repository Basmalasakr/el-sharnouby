import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from theme import header, kpi, insight, plot

DATA_DIR = "data/"
CH = {"LOC001": "Retail", "LOC002": "Online", "LOC003": "Wholesale"}

st.set_page_config(layout="wide", page_title="Marketing Attribution")
header("Marketing Attribution & Growth Engine", "Which spend creates profitable customers? Analyze ROAS, Funnels, and Over-attribution.", "APP 05")

@st.cache_data(show_spinner=False)
def load_marketing_data():
    try:
        mkt = pd.read_csv(DATA_DIR + "Marketing.csv")
    except:
        try:
            mkt = pd.read_parquet(DATA_DIR + "Marketing.parquet")
        except:
            mkt = pd.DataFrame()

    try:
        web = pd.read_csv(DATA_DIR + "Web_Traffic_Daily.csv")
    except:
        try:
            web = pd.read_parquet(DATA_DIR + "Web_Traffic_Daily.parquet")
        except:
            web = pd.DataFrame()
    
    try:
        sales = pd.read_csv(DATA_DIR + "Sales_Transactions.csv")
    except:
        try:
            sales = pd.read_parquet(DATA_DIR + "Sales_Transactions.parquet")
        except:
            sales = pd.DataFrame()
            
    if mkt.empty and web.empty and sales.empty:
        st.error("Marketing and Sales data are missing! Please ensure the files are in the data folder.")
        st.stop()
        
    if not sales.empty:
        if "Location_ID" in sales.columns:
            sales["Channel"] = sales["Location_ID"].map(CH).fillna(sales["Location_ID"])
        elif "Location_Name" in sales.columns:
            sales["Channel"] = sales["Location_Name"]
        else:
            sales["Channel"] = "Unknown"
        if 'Order_Date' in sales.columns: 
            sales['Order_Date'] = pd.to_datetime(sales['Order_Date'], errors='coerce')

    if not mkt.empty and 'Start_Date' in mkt.columns: 
        mkt['Start_Date'] = pd.to_datetime(mkt['Start_Date'], errors='coerce')
    if not web.empty and 'Date' in web.columns: 
        web['Date'] = pd.to_datetime(web['Date'], errors='coerce')
        
    return mkt, web, sales

mkt_raw, web_raw, sales_raw = load_marketing_data()

min_date = pd.to_datetime('2024-01-01').date() 
max_date = pd.to_datetime('today').date()
try:
    dates_list = []
    if not mkt_raw.empty: dates_list.append(mkt_raw['Start_Date'].dropna())
    if not web_raw.empty: dates_list.append(web_raw['Date'].dropna())
    if not sales_raw.empty: dates_list.append(sales_raw['Order_Date'].dropna())
    
    if dates_list:
        all_dates = pd.concat(dates_list)
        if not all_dates.empty:
            min_date = all_dates.min().date()
            max_date = all_dates.max().date()
except:
    pass

with st.form("date_filter_form"):
    c1, c2 = st.columns([4, 1])
    with c1:
        date_range = st.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    with c2:
        st.markdown("<div style='margin-top: 27px;'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Apply Filter", use_container_width=True)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_dt, end_dt = date_range
    start_dt = pd.to_datetime(start_dt)
    end_dt = pd.to_datetime(end_dt)
    
    mkt = mkt_raw[(mkt_raw['Start_Date'] >= start_dt) & (mkt_raw['Start_Date'] <= end_dt)] if not mkt_raw.empty else mkt_raw
    web = web_raw[(web_raw['Date'] >= start_dt) & (web_raw['Date'] <= end_dt)] if not web_raw.empty else web_raw
    sales = sales_raw[(sales_raw['Order_Date'] >= start_dt) & (sales_raw['Order_Date'] <= end_dt)] if not sales_raw.empty else sales_raw
else:
    mkt, web, sales = mkt_raw, web_raw, sales_raw

t1, t2, t3 = st.tabs(["1. ROI & Over-Attribution", "2. Web Conversion Funnel", "3. AI Budget Optimizer"])

with t1:
    total_spend = mkt['Spend_EGP'].sum() if not mkt.empty else 0
    claimed_orders = mkt['Orders_Attributed'].sum() if not mkt.empty else 0
    claimed_revenue = mkt['Attributed_Revenue_EGP'].sum() if not mkt.empty else 0
    avg_roas = claimed_revenue / total_spend if total_spend > 0 else 0
    avg_cac = total_spend / claimed_orders if claimed_orders > 0 else 0
    
    sales_net = sales['Net_Sales_EGP'] if not sales.empty and 'Net_Sales_EGP' in sales.columns else (sales['Gross_Sales_EGP'] if not sales.empty and 'Gross_Sales_EGP' in sales.columns else pd.Series())
    actual_online_rev = sales[sales['Channel'].str.contains("Online", case=False, na=False)][sales_net.name].sum() if not sales.empty and not sales_net.empty else 0
    
    over_attribution_gap = claimed_revenue - actual_online_rev
    over_attr_pct = (over_attribution_gap / actual_online_rev) * 100 if actual_online_rev > 0 else 0
    
    r1 = st.columns(5)
    r1[0].markdown(kpi("Total Ad Spend", f"{total_spend/1e6:,.2f}M EGP", "Cross-platform spend", "info"), unsafe_allow_html=True)
    r1[1].markdown(kpi("Reported ROAS", f"{avg_roas:.2f}x", "Revenue / Spend", "ok" if avg_roas > 4 else "warn"), unsafe_allow_html=True)
    r1[2].markdown(kpi("Avg CAC", f"{avg_cac:,.0f} EGP", "Cost per Acquisition", "info"), unsafe_allow_html=True)
    r1[3].markdown(kpi("Claimed Revenue", f"{claimed_revenue/1e6:,.1f}M EGP", "Reported by Ad Platforms", "info"), unsafe_allow_html=True)
    r1[4].markdown(kpi("Actual Online Rev", f"{actual_online_rev/1e6:,.1f}M EGP", "From Sales DB", "ok"), unsafe_allow_html=True)
    
    st.write("")
    if over_attribution_gap > 0:
        insight(f"**Attribution Caveat:** Ad platforms are claiming **{claimed_revenue/1e6:,.1f}M EGP**, but actual online sales are only **{actual_online_rev/1e6:,.1f}M EGP**. This is a **{over_attr_pct:.1f}% over-attribution gap** (double-counting conversions across platforms). Adjust ROAS expectations accordingly.")
    else:
        insight("Ad platform tracking aligns well with actual recorded online sales.")
    
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**ROAS & CAC by Platform**")
        if not mkt.empty:
            platform_perf = mkt.groupby('Platform').agg(
                Spend=('Spend_EGP', 'sum'),
                Revenue=('Attributed_Revenue_EGP', 'sum'),
                Orders=('Orders_Attributed', 'sum')
            ).reset_index()
            platform_perf['ROAS'] = platform_perf['Revenue'] / platform_perf['Spend'].replace(0, 1)
            platform_perf['CAC (EGP)'] = platform_perf['Spend'] / platform_perf['Orders'].replace(0, 1)
            
            fig_bubble = px.scatter(platform_perf, x='CAC (EGP)', y='ROAS', size='Spend', color='Platform',
                                    hover_name='Platform', size_max=40, text='Platform', 
                                    color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_bubble.update_traces(textposition='top center')
            fig_bubble.add_hline(y=3.0, line_dash="dash", line_color="red", annotation_text="Break-even ROAS")
            plot(fig_bubble, 350)
        else:
            st.info("No data available for the selected period.")
        
    with c2, st.container(border=True):
        st.markdown("**Platform Performance Detail**")
        if not mkt.empty:
            disp = platform_perf.sort_values('ROAS', ascending=False)
            disp['Spend'] = disp['Spend'].apply(lambda x: f"{x:,.0f}")
            disp['Revenue'] = disp['Revenue'].apply(lambda x: f"{x:,.0f}")
            disp['ROAS'] = disp['ROAS'].apply(lambda x: f"{x:.2f}x")
            disp['CAC (EGP)'] = disp['CAC (EGP)'].apply(lambda x: f"{x:,.0f}")
            st.dataframe(disp, use_container_width=True, hide_index=True)
        else:
            st.info("No data available.")

with t2:
    total_sessions = web['Sessions'].sum() if not web.empty else 0
    total_atc = int((web['Add_To_Cart_Rate'] * web['Sessions']).sum()) if not web.empty else 0
    total_chk = int((web['Checkout_Rate'] * web['Sessions']).sum()) if not web.empty else 0
    total_orders = web['Orders'].sum() if not web.empty else 0
    
    funnel_data = dict(
        number=[total_sessions, total_atc, total_chk, total_orders],
        stage=["Website Sessions", "Added to Cart", "Initiated Checkout", "Successful Orders"]
    )
    
    avg_cr = (total_orders / total_sessions) * 100 if total_sessions > 0 else 0
    avg_load_time = web['Avg_Page_Load_Sec'].mean() if not web.empty else 0
    
    r2 = st.columns(3)
    r2[0].markdown(kpi("Total Sessions", f"{total_sessions:,.0f}", "Website Traffic", "info"), unsafe_allow_html=True)
    r2[1].markdown(kpi("Overall Conversion Rate", f"{avg_cr:.2f}%", "Sessions to Orders", "ok" if avg_cr > 2 else "warn"), unsafe_allow_html=True)
    r2[2].markdown(kpi("Avg Page Load Time", f"{avg_load_time:.1f} sec", "Impacts bounce rate", "warn" if avg_load_time > 3 else "ok"), unsafe_allow_html=True)
    
    st.write("")
    
    f1, f2 = st.columns([1.5, 1])
    with f1, st.container(border=True):
        st.markdown("**E-commerce Conversion Funnel**")
        if total_sessions > 0:
            fig_funnel = go.Figure(go.Funnel(
                y=funnel_data["stage"],
                x=funnel_data["number"],
                textinfo="value+percent initial",
                marker={"color": ["#1D4ED8", "#3B82F6", "#60A5FA", "#93C5FD"]}
            ))
            fig_funnel.update_layout(margin=dict(t=10, b=0, l=0, r=0))
            plot(fig_funnel, 350)
        else:
            st.info("No funnel data available for this period.")
        
    with f2, st.container(border=True):
        st.markdown("**Traffic Quality vs Conversion**")
        if not web.empty:
            fig_trend = px.scatter(web, x='Avg_Page_Load_Sec', y='Conversion_Rate', 
                                   color='Mobile_Pct', color_continuous_scale='Viridis',
                                   labels={"Avg_Page_Load_Sec": "Load Time (Sec)", "Conversion_Rate": "Conversion Rate %"})
            fig_trend.update_layout(margin=dict(t=10, b=0, l=0, r=0))
            plot(fig_trend, 350)
        else:
            st.info("No traffic data available.")

with t3:
    st.markdown("### Prescriptive Budget Reallocation")
    st.caption("AI-based recommendations to shift ad spend from low-performing campaigns to high-yielding ones based on ROAS and CAC.")
    
    if not mkt.empty:
        mkt_opt = mkt.copy()
        mkt_opt['ROAS'] = mkt_opt['Attributed_Revenue_EGP'] / mkt_opt['Spend_EGP'].replace(0, 1)
        mkt_opt['CAC'] = mkt_opt['Spend_EGP'] / mkt_opt['Orders_Attributed'].replace(0, 1)
        
        target_roas = 4.0
        poor_roas = 2.5
        
        recommendations = []
        for _, row in mkt_opt.iterrows():
            camp = row['Campaign_Name']
            plat = row['Platform']
            spend = row['Spend_EGP']
            roas = row['ROAS']
            cac = row['CAC']
            
            if spend < 1000: continue
            
            if roas >= target_roas:
                action = "Scale Up (Increase Budget)"
                reason = f"Excellent ROAS ({roas:.1f}x) & low CAC ({cac:,.0f} EGP)."
            elif roas <= poor_roas:
                action = "Kill or Pause (Reallocate)"
                reason = f"Poor ROAS ({roas:.1f}x) is bleeding budget. CAC is too high ({cac:,.0f} EGP)."
            else:
                action = "Optimize (A/B Test Creatives)"
                reason = f"Average performance. Needs better CTR or Conversion Rate."
                
            recommendations.append({
                "Platform": plat,
                "Campaign": camp,
                "Spend_EGP": f"{spend:,.0f}",
                "Current_ROAS": f"{roas:.1f}x",
                "AI Action": action,
                "Logic": reason
            })
            
        if recommendations:
            rec_df = pd.DataFrame(recommendations).sort_values(by="AI Action")
            st.dataframe(rec_df, use_container_width=True, hide_index=True)
        else:
            st.success("All campaigns are operating within optimal bounds for the selected period.")
    else:
        st.info("No marketing data available for the selected period.")