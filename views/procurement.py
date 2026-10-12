import os
import pandas as pd
import plotly.express as px
import streamlit as st
from theme import header, kpi, insight, plot

DATA_DIR = "data/"
st.set_page_config(layout="wide", page_title="Procurement & Risk")
header("Procurement, Cost & Supplier Risk", "Where do cost, delay, and quality risk begin?", "APP 07")

required_files = ["Purchase_Orders.csv", "Suppliers.csv", "Materials.csv", "Product_BOM.csv"]
missing_files = [f for f in required_files if not os.path.exists(DATA_DIR + f)]
if missing_files:
    st.error(f"Missing files: {', '.join(missing_files)}.")
    st.stop()

@st.cache_data(show_spinner=False)
def load_procurement_data():
    po = pd.read_csv(DATA_DIR + "Purchase_Orders.csv")
    sup = pd.read_csv(DATA_DIR + "Suppliers.csv")
    mat = pd.read_csv(DATA_DIR + "Materials.csv")
    bom = pd.read_csv(DATA_DIR + "Product_BOM.csv")
    
    for col in ['Order_Date', 'Promised_Date', 'Actual_Receipt_Date']:
        if col in po.columns:
            po[col] = pd.to_datetime(po[col], errors='coerce')
            
    if 'Promised_Date' in po.columns and 'Actual_Receipt_Date' in po.columns:
        po['Delay_Days'] = (po['Actual_Receipt_Date'] - po['Promised_Date']).dt.days
        po['Is_Late'] = po['Delay_Days'] > 0
        
    if 'Accepted_Qty' in po.columns and 'Rejected_Qty' in po.columns:
        po['Total_Received'] = po['Accepted_Qty'] + po['Rejected_Qty']
        po['Reject_Rate'] = po['Rejected_Qty'] / po['Total_Received'].replace(0, 1)
        
    return po, sup, mat, bom

po, sup, mat, bom = load_procurement_data()

po_sup = pd.merge(po, sup[['Supplier_ID', 'Supplier_Name']], on='Supplier_ID', how='left')
po_sup['Supplier_Name'] = po_sup['Supplier_Name'].fillna(po_sup['Supplier_ID'])

t1, t2, t3 = st.tabs(["1. Supplier Risk Matrix", "2. Material Cost Trends", "3. BOM & Single-Source Exposure"])

with t1:
    sup_perf = po_sup.groupby('Supplier_Name').agg(
        Total_Orders=('PO_ID', 'count'),
        Late_Orders=('Is_Late', 'sum'),
        Avg_Delay_Days=('Delay_Days', lambda x: x[x > 0].mean()),
        Total_Received=('Total_Received', 'sum'),
        Total_Rejected=('Rejected_Qty', 'sum'),
        Total_Spend=('Unit_Cost_EGP', 'sum')
    ).reset_index()
    
    sup_perf['On_Time_Pct'] = (1 - (sup_perf['Late_Orders'] / sup_perf['Total_Orders'])) * 100
    sup_perf['Reject_Pct'] = (sup_perf['Total_Rejected'] / sup_perf['Total_Received'].replace(0, 1)) * 100
    sup_perf['Avg_Delay_Days'] = sup_perf['Avg_Delay_Days'].fillna(0)
    
    overall_on_time = (1 - (sup_perf['Late_Orders'].sum() / sup_perf['Total_Orders'].sum())) * 100 if sup_perf['Total_Orders'].sum() > 0 else 0
    overall_reject = (sup_perf['Total_Rejected'].sum() / sup_perf['Total_Received'].sum()) * 100 if sup_perf['Total_Received'].sum() > 0 else 0
    high_risk_sups = sup_perf[(sup_perf['On_Time_Pct'] < 80) | (sup_perf['Reject_Pct'] > 5)]
    
    r1 = st.columns(4)
    r1[0].markdown(kpi("Overall On-Time Delivery", f"{overall_on_time:.1f}%", "Target: > 90%", "warn" if overall_on_time < 90 else "ok"), unsafe_allow_html=True)
    r1[1].markdown(kpi("Overall Reject Rate", f"{overall_reject:.2f}%", "Target: < 2%", "bad" if overall_reject > 2 else "ok"), unsafe_allow_html=True)
    r1[2].markdown(kpi("Active Suppliers", f"{len(sup_perf)}", "Registered in POs", "info"), unsafe_allow_html=True)
    r1[3].markdown(kpi("High-Risk Suppliers", f"{len(high_risk_sups)}", "Below SLA thresholds", "bad" if len(high_risk_sups) > 0 else "ok"), unsafe_allow_html=True)
    
    st.write("")
    
    if not high_risk_sups.empty:
        worst_sups = ", ".join(high_risk_sups['Supplier_Name'].head(3).tolist())
        with st.container(border=True):
            st.markdown(f"**EXECUTIVE ALERT:** Suppliers **{worst_sups}** are critically underperforming against SLAs (low on-time rate or high defect rate). Immediate contract review or secondary sourcing is required to prevent production halts.")
    
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**Supplier Risk Matrix (Delay vs Quality)**")
        fig_risk = px.scatter(
            sup_perf, x='Reject_Pct', y='On_Time_Pct', size='Total_Orders', color='Supplier_Name',
            hover_name='Supplier_Name',
            labels={'Reject_Pct': 'Reject Rate (%)', 'On_Time_Pct': 'On-Time Delivery (%)'},
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_risk.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="Min On-Time (80%)")
        fig_risk.add_vline(x=5, line_dash="dash", line_color="red", annotation_text="Max Reject (5%)")
        plot(fig_risk, 350)
        
    with c2, st.container(border=True):
        st.markdown("**Supplier Performance Leaderboard**")
        disp_sup = sup_perf[['Supplier_Name', 'On_Time_Pct', 'Reject_Pct', 'Avg_Delay_Days', 'Total_Orders']].sort_values('On_Time_Pct')
        disp_sup['On_Time_Pct'] = disp_sup['On_Time_Pct'].apply(lambda x: f"{x:.1f}%")
        disp_sup['Reject_Pct'] = disp_sup['Reject_Pct'].apply(lambda x: f"{x:.2f}%")
        disp_sup['Avg_Delay_Days'] = disp_sup['Avg_Delay_Days'].apply(lambda x: f"{x:.1f}")
        st.dataframe(disp_sup, use_container_width=True, hide_index=True)

with t2:
    st.markdown("**Material Cost Inflation (2023 - Present)**")
    
    if 'Order_Date' in po.columns and 'Unit_Cost_EGP' in po.columns:
        po_cost = po.dropna(subset=['Order_Date', 'Unit_Cost_EGP']).copy()
        po_cost['YearMonth'] = po_cost['Order_Date'].dt.to_period('M').astype(str)
        
        top_mats = po_cost['Material_Name'].value_counts().head(5).index
        trend_data = po_cost[po_cost['Material_Name'].isin(top_mats)]
        
        trend_agg = trend_data.groupby(['YearMonth', 'Material_Name'])['Unit_Cost_EGP'].mean().reset_index()
        trend_agg = trend_agg.sort_values('YearMonth')
        
        fig_trend = px.line(
            trend_agg, x='YearMonth', y='Unit_Cost_EGP', color='Material_Name', markers=True,
            labels={'YearMonth': 'Order Date', 'Unit_Cost_EGP': 'Avg Unit Cost (EGP)', 'Material_Name': 'Material'},
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        plot(fig_trend, 400)
    else:
        st.info("Sufficient historical cost data is not available.")

with t3:
    st.markdown("**BOM Vulnerability & Single-Source Exposure**")
    
    mat_sup_count = po_sup.groupby('Material_Name')['Supplier_ID'].nunique().reset_index()
    mat_sup_count.columns = ['Material_Name', 'Available_Suppliers']
    
    latest_costs = po.sort_values('Order_Date').groupby('Material_Name').tail(1)[['Material_Name', 'Unit_Cost_EGP']]
    
    bom_analysis = pd.merge(bom, mat_sup_count, on='Material_Name', how='left')
    bom_analysis = pd.merge(bom_analysis, latest_costs, on='Material_Name', how='left')
    bom_analysis['Material_Cost_Contribution'] = bom_analysis['Required_Per_Unit'] * bom_analysis['Unit_Cost_EGP']
    bom_analysis['Available_Suppliers'] = bom_analysis['Available_Suppliers'].fillna(0).astype(int)
    
    product_risk = bom_analysis.groupby('Product_Name').agg(
        Total_BOM_Cost=('Material_Cost_Contribution', 'sum'),
        Total_Components=('Material_ID', 'count'),
        Single_Source_Risk=('Available_Suppliers', lambda x: (x == 1).sum()) 
    ).reset_index().sort_values('Single_Source_Risk', ascending=False)
    
    product_risk['Total_BOM_Cost'] = product_risk['Total_BOM_Cost'].apply(lambda x: f"{x:,.2f} EGP")
    
    c1, c2 = st.columns([1, 1])
    with c1, st.container(border=True):
        st.markdown("**Product Risk Profile**")
        st.caption("Products highly dependent on single-sourced materials.")
        st.dataframe(product_risk, use_container_width=True, hide_index=True)
        
    with c2, st.container(border=True):
        st.markdown("**BOM Cost Breakdown by Product**")
        if not bom_analysis.empty:
            selected_prod = st.selectbox("Select Product to Inspect:", product_risk['Product_Name'].tolist())
            prod_bom = bom_analysis[bom_analysis['Product_Name'] == selected_prod][['Material_Name', 'Required_Per_Unit', 'Unit_Cost_EGP', 'Material_Cost_Contribution', 'Available_Suppliers']]
            prod_bom['Material_Cost_Contribution'] = prod_bom['Material_Cost_Contribution'].apply(lambda x: f"{x:,.2f} EGP")
            
            def highlight_risk(val):
                color = '#EF4444' if val == 1 else ''
                return f'background-color: {color}'
            st.dataframe(prod_bom.style.map(highlight_risk, subset=['Available_Suppliers']), use_container_width=True, hide_index=True)    
