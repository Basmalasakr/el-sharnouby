import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from theme import header, kpi, insight, plot

DATA_DIR = "data/"

st.set_page_config(layout="wide", page_title="Factory Digital Twin", page_icon="")
header("Factory Digital Twin & Production Control", "Monitor production orders, quality losses, and machine bottlenecks.", "APP 04")

@st.cache_data(show_spinner=False)
def load_factory_data():
    
    # 1. Production Orders
    try:
        po = pd.read_csv(DATA_DIR + "Production_Orders.csv")
    except:
        try:
            po = pd.read_parquet(DATA_DIR + "Production_Orders.parquet")
        except:
            po = pd.DataFrame()

    # 2. Machine Downtime
    try:
        md = pd.read_csv(DATA_DIR + "Machine_Downtime.csv")
    except:
        try:
            md = pd.read_parquet(DATA_DIR + "Machine_Downtime.parquet")
        except:
            md = pd.DataFrame()

    # 3. Quality
    try:
        qc = pd.read_csv(DATA_DIR + "Quality.csv")
    except:
        try:
            qc = pd.read_parquet(DATA_DIR + "Quality.parquet")
        except:
            qc = pd.DataFrame()

    # 4. Printing Batches
    try:
        pb = pd.read_csv(DATA_DIR + "Printing_Batches.csv")
    except:
        try:
            pb = pd.read_parquet(DATA_DIR + "Printing_Batches.parquet")
        except:
            pb = pd.DataFrame()
            
    date_cols = {
        'Start_Date': po, 'Due_Date': po, 'Completion_Date': po,
        'Date': md, 'Inspection_Date': qc, 'Print_Date': pb
    }
    for col, df in date_cols.items():
        if col in df.columns and not df.empty:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
    if 'Planned' in md.columns and not md.empty:
        md['Planned'] = md['Planned'].astype(str).str.lower().map({'true': True, 'yes': True, '1': True, 'false': False, 'no': False, '0': False}).fillna(False)
            
    return po, md, qc, pb

po, md, qc, pb = load_factory_data()

# التحقق من وجود بيانات (عشان لو ملقاش أي حاجة خالص يطلع رسالة شيك)
if po.empty and md.empty and qc.empty and pb.empty:
    st.error("⚠️ No Factory Data found! Please ensure your CSV or Parquet files are in the 'data' folder.")
    st.stop()

with st.container(border=True):
    st.markdown("**Capacity Simulator**")
    st.caption("Simulate the impact of increasing overtime on delayed orders.")
    ot_sim = st.slider("Simulate Overtime Increase (%)", 0, 50, 0, 5)

t1, t2, t3 = st.tabs(["1. Production & Bottlenecks", "2. Quality & Pareto Analysis", "3. Equipment & Maintenance"])

with t1:
    if not po.empty:
        total_orders = len(po)
        base_late_orders = len(po[po['Delay_Days'] > 0]) if 'Delay_Days' in po.columns else 0
        
        recovered_orders = int(base_late_orders * (ot_sim / 100.0) * 0.8)
        sim_late_orders = base_late_orders - recovered_orders
        late_pct = (sim_late_orders / total_orders) * 100 if total_orders > 0 else 0
        
        avg_eff = po['Efficiency_Pct'].mean() if 'Efficiency_Pct' in po.columns else 0
        
        planned_qty = po['Planned_Qty'].sum() if 'Planned_Qty' in po.columns else 0
        good_qty = po['Good_Qty'].sum() if 'Good_Qty' in po.columns else 0
        completion_rate = (good_qty / planned_qty) * 100 if planned_qty > 0 else 0
        
        r1 = st.columns(4)
        r1[0].markdown(kpi("Total Orders", f"{total_orders:,}", "Tracked in system", "info"), unsafe_allow_html=True)
        r1[1].markdown(kpi("Late Orders", f"{sim_late_orders:,}", f"{(base_late_orders - sim_late_orders):,} recovered via simulation" if ot_sim > 0 else f"{late_pct:.1f}% of total", "warn" if late_pct > 15 else "ok"), unsafe_allow_html=True)
        r1[2].markdown(kpi("Plan Completion", f"{completion_rate:.1f}%", "Good Qty vs Planned", "ok" if completion_rate >= 90 else "warn"), unsafe_allow_html=True)
        r1[3].markdown(kpi("Avg Line Efficiency", f"{avg_eff:.1f}%", "OEE Target: 85%", "ok" if avg_eff >= 85 else "bad"), unsafe_allow_html=True)
        
        st.write("")
        if 'Primary_Bottleneck' in po.columns:
            top_bottleneck = po['Primary_Bottleneck'].mode()[0] if not po['Primary_Bottleneck'].empty else "Unknown"
            delayed_by_top = len(po[(po['Delay_Days'] > 0) & (po['Primary_Bottleneck'] == top_bottleneck)]) if 'Delay_Days' in po.columns else 0
            insight(f"**{top_bottleneck}** is the primary bottleneck, causing **{delayed_by_top}** delayed orders. Focusing simulation overtime here yields the highest ROI.")
        
        a, b = st.columns([1, 1.2])
        with a, st.container(border=True):
            st.markdown("**Delayed Orders by Bottleneck**")
            if 'Primary_Bottleneck' in po.columns and 'Delay_Days' in po.columns:
                delay_df = po[po['Delay_Days'] > 0].groupby('Primary_Bottleneck').size().reset_index(name='Late Orders')
                if not delay_df.empty:
                    fig_bn = px.bar(delay_df, x='Late Orders', y='Primary_Bottleneck', orientation='h', color='Primary_Bottleneck', color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_bn.update_layout(showlegend=False, margin=dict(t=10, b=0, l=0, r=0), yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_bn, use_container_width=True)
                
        with b, st.container(border=True):
            st.markdown("**Critical Late Orders (Requires Attention)**")
            if 'Delay_Days' in po.columns:
                late_po = po[po['Delay_Days'] > 0].sort_values('Delay_Days', ascending=False).head(8)
                if not late_po.empty:
                    display_cols = ['Production_Order_ID', 'Product_Name', 'Planned_Qty', 'Delay_Days', 'Primary_Bottleneck']
                    late_display = late_po[[c for c in display_cols if c in late_po.columns]]
                    st.dataframe(late_display, use_container_width=True, hide_index=True)
    else:
        st.info("Production Orders data is missing.")

with t2:
    if not qc.empty:
        inspected = qc['Inspected_Qty'].sum() if 'Inspected_Qty' in qc.columns else 0
        rejected = qc['Rejected_Qty'].sum() if 'Rejected_Qty' in qc.columns else 0
        scrap_rate = (rejected / inspected) * 100 if inspected > 0 else 0
        total_loss = qc['Estimated_Loss_EGP'].sum() if 'Estimated_Loss_EGP' in qc.columns else 0
        
        r2 = st.columns(4)
        r2[0].markdown(kpi("Inspected Units", f"{inspected:,.0f}", "Total Qty Checked", "info"), unsafe_allow_html=True)
        r2[1].markdown(kpi("Rejected Units", f"{rejected:,.0f}", "Failed Quality Control", "warn"), unsafe_allow_html=True)
        r2[2].markdown(kpi("Scrap Rate", f"{scrap_rate:.2f}%", "Target: < 2.0%", "bad" if scrap_rate > 2 else "ok"), unsafe_allow_html=True)
        r2[3].markdown(kpi("Financial Loss", f"{total_loss/1e6:,.2f}M EGP", "Estimated Scrap Cost", "bad"), unsafe_allow_html=True)
        
        st.write("")
        
        if 'Defect_Type' in qc.columns and 'Estimated_Loss_EGP' in qc.columns:
            defect_loss = qc.groupby('Defect_Type')['Estimated_Loss_EGP'].sum().sort_values(ascending=False).reset_index()
            if not defect_loss.empty and defect_loss['Estimated_Loss_EGP'].sum() > 0:
                defect_loss['Cum_Pct'] = defect_loss['Estimated_Loss_EGP'].cumsum() / defect_loss['Estimated_Loss_EGP'].sum() * 100
                pareto_defects = defect_loss[defect_loss['Cum_Pct'] <= 80]
                top_defect_names = ", ".join(pareto_defects['Defect_Type'].tolist())
                insight(f"**Pareto Principle (80/20):** 80% of our financial losses are driven by these critical defects: **{top_defect_names}**. Immediate root-cause analysis required here.")
            
        c1, c2 = st.columns(2)
        with c1, st.container(border=True):
            st.markdown("**Financial Loss by Defect Type**")
            if 'Defect_Type' in qc.columns and 'Estimated_Loss_EGP' in qc.columns and not defect_loss.empty:
                fig_def = px.pie(defect_loss, values='Estimated_Loss_EGP', names='Defect_Type', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
                fig_def.update_layout(margin=dict(t=10, b=0, l=0, r=0))
                st.plotly_chart(fig_def, use_container_width=True)
                
        with c2, st.container(border=True):
            st.markdown("**Top Products with Quality Issues**")
            if 'Product_Name' in qc.columns and 'Estimated_Loss_EGP' in qc.columns:
                prod_loss = qc.groupby(['Product_ID', 'Product_Name']).agg(
                    Rejected=('Rejected_Qty', 'sum'),
                    Loss_EGP=('Estimated_Loss_EGP', 'sum')
                ).reset_index().sort_values('Loss_EGP', ascending=False).head(6)
                
                prod_loss['Loss_EGP'] = (prod_loss['Loss_EGP'] / 1000).apply(lambda x: f"{x:,.1f}K")
                st.dataframe(prod_loss, use_container_width=True, hide_index=True)
    else:
         st.info("Quality data is missing.")

with t3:
    unplanned_md = md[md['Planned'] == False] if not md.empty and 'Planned' in md.columns else md
    total_downtime = unplanned_md['Downtime_Hours'].sum() if not unplanned_md.empty and 'Downtime_Hours' in unplanned_md.columns else 0
    rework_cost = pb['Rework_Cost_EGP'].sum() if not pb.empty and 'Rework_Cost_EGP' in pb.columns else 0
    reprint_qty = pb['Reprint_Qty'].sum() if not pb.empty and 'Reprint_Qty' in pb.columns else 0
    
    r3 = st.columns(3)
    r3[0].markdown(kpi("Unplanned Downtime", f"{total_downtime:,.1f} Hrs", "Machine breakdown time", "bad"), unsafe_allow_html=True)
    r3[1].markdown(kpi("Printing Rework Cost", f"{rework_cost/1e3:,.1f}K EGP", "Due to print defects", "warn"), unsafe_allow_html=True)
    r3[2].markdown(kpi("Reprinted Units", f"{reprint_qty:,.0f} Units", "Wasted printing capacity", "warn"), unsafe_allow_html=True)
    
    st.write("")
    
    d1, d2 = st.columns([1, 1])
    with d1, st.container(border=True):
        st.markdown("**Prescriptive Maintenance Priorities**")
        if not unplanned_md.empty and 'Machine_ID' in unplanned_md.columns and 'Downtime_Hours' in unplanned_md.columns:
            priority = unplanned_md.groupby(['Machine_ID', 'Reason']).agg(
                Incidents=('Downtime_Hours', 'count'),
                Total_Hours=('Downtime_Hours', 'sum')
            ).reset_index().sort_values('Total_Hours', ascending=False).head(8)
            
            if not priority.empty:
                risk_threshold = priority['Total_Hours'].quantile(0.75)
                priority['Risk_Level'] = np.where(priority['Total_Hours'] >= risk_threshold, 'High', 'Medium')
                st.dataframe(priority[['Machine_ID', 'Reason', 'Total_Hours', 'Risk_Level']], use_container_width=True, hide_index=True)
            
    with d2, st.container(border=True):
        st.markdown("**Printing Department Issues (Rework)**")
        if not pb.empty and 'Reprint_Qty' in pb.columns:
            print_issues = pb[pb['Reprint_Qty'] > 0].groupby(['Product_Name', 'Defect_Type']).agg(
                Reprint_Qty=('Reprint_Qty', 'sum'),
                Cost=('Rework_Cost_EGP', 'sum')
            ).reset_index().sort_values('Cost', ascending=False).head(6)
            
            if not print_issues.empty:
                print_issues['Cost'] = (print_issues['Cost'] / 1000).apply(lambda x: f"{x:,.1f}K")
                st.dataframe(print_issues, use_container_width=True, hide_index=True)
            else:
                 st.info("No printing batches data available with rework.")
        else:
            st.info("No printing batches data available.")