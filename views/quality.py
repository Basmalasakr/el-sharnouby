import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from theme import header, kpi, plot

DATA_DIR = "data/"
st.set_page_config(layout="wide", page_title="Quality & Returns")
header("Quality & Returns Analytics", "Which defects and root causes cost the most?", "APP 08")

@st.cache_data(show_spinner=False)
def load_quality_data():
    try:
        qual = pd.read_csv(DATA_DIR + "Quality.csv")
    except:
        try:
            qual = pd.read_parquet(DATA_DIR + "Quality.parquet")
        except:
            qual = pd.DataFrame()
            
    try:
        print_b = pd.read_csv(DATA_DIR + "Printing_Batches.csv")
    except:
        try:
            print_b = pd.read_parquet(DATA_DIR + "Printing_Batches.parquet")
        except:
            print_b = pd.DataFrame()
    
    try:
        sales = pd.read_csv(DATA_DIR + "Sales_Transactions.csv")
    except:
        try:
            sales = pd.read_parquet(DATA_DIR + "Sales_Transactions.parquet")
        except:
            sales = pd.DataFrame()
            
    return qual, print_b, sales

qual, print_b, sales = load_quality_data()

if qual.empty and print_b.empty:
    st.error("Quality and Printing data are required for this module.")
    st.stop()

total_quality_loss = qual['Estimated_Loss_EGP'].sum() if not qual.empty and 'Estimated_Loss_EGP' in qual.columns else 0
total_print_rework = print_b['Rework_Cost_EGP'].sum() if not print_b.empty and 'Rework_Cost_EGP' in print_b.columns else 0
total_financial_impact = total_quality_loss + total_print_rework

total_inspected = qual['Inspected_Qty'].sum() if not qual.empty and 'Inspected_Qty' in qual.columns else 1
total_rejected = qual['Rejected_Qty'].sum() if not qual.empty and 'Rejected_Qty' in qual.columns else 0
overall_defect_rate = (total_rejected / total_inspected) * 100 if total_inspected > 0 else 0

if not qual.empty and 'Root_Cause' in qual.columns and 'Estimated_Loss_EGP' in qual.columns:
    pareto_df = qual.groupby('Root_Cause')['Estimated_Loss_EGP'].sum().reset_index()
    pareto_df = pareto_df.sort_values(by='Estimated_Loss_EGP', ascending=False)
    pareto_df['Cumulative_Pct'] = (pareto_df['Estimated_Loss_EGP'].cumsum() / pareto_df['Estimated_Loss_EGP'].sum()) * 100
    top_root_cause = pareto_df.iloc[0]['Root_Cause'] if not pareto_df.empty else "Unknown"
    top_cause_loss = pareto_df.iloc[0]['Estimated_Loss_EGP'] if not pareto_df.empty else 0
else:
    pareto_df = pd.DataFrame()
    top_root_cause = "Unknown"
    top_cause_loss = 0

r1 = st.columns(4)
r1[0].markdown(kpi("Total Quality Loss", f"{total_financial_impact/1e6:.1f}M EGP", "Factory + Printing", "bad"), unsafe_allow_html=True)
r1[1].markdown(kpi("Printing Rework", f"{total_print_rework/1e3:.0f}K EGP", "Ink & Consumable", "warn"), unsafe_allow_html=True)
r1[2].markdown(kpi("Overall Defect Rate", f"{overall_defect_rate:.2f}%", "Factory rejection", "info"), unsafe_allow_html=True)
r1[3].markdown(kpi("Top Root Cause", str(top_root_cause), f"Loss: {top_cause_loss/1e6:.1f}M EGP", "bad"), unsafe_allow_html=True)

st.write("")

if not pareto_df.empty:
    with st.container(border=True):
        st.markdown(f"**EXECUTIVE RECOMMENDATION:** The root cause **'{top_root_cause}'** is responsible for the highest financial leakage (**{top_cause_loss:,.0f} EGP**). Implementing targeted corrective actions on this single variable will yield the highest return on investment in quality control.")

t1, t2 = st.tabs(["1. Defect Pareto & Financial Impact", "2. Corrective Action Priority Matrix"])

with t1:
    c1, c2 = st.columns([1.5, 1])
    
    with c1, st.container(border=True):
        st.markdown("**Financial Loss by Root Cause (Pareto Chart)**")
        if not pareto_df.empty:
            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(
                x=pareto_df['Root_Cause'],
                y=pareto_df['Estimated_Loss_EGP'],
                name='Loss (EGP)',
                marker_color='#3B82F6'
            ))
            fig_pareto.add_trace(go.Scatter(
                x=pareto_df['Root_Cause'],
                y=pareto_df['Cumulative_Pct'],
                name='Cumulative %',
                mode='lines+markers',
                yaxis='y2',
                marker_color='#EF4444'
            ))
            fig_pareto.update_layout(
                yaxis=dict(title='Estimated Loss (EGP)'),
                yaxis2=dict(title='Cumulative %', overlaying='y', side='right', range=[0, 105]),
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            plot(fig_pareto, 400)
        else:
            st.info("Insufficient data for Pareto analysis.")
            
    with c2, st.container(border=True):
        st.markdown("**Defects by Stage & Product**")
        if not qual.empty and 'Stage' in qual.columns:
            stage_loss = qual.groupby('Stage')['Estimated_Loss_EGP'].sum().reset_index()
            fig_stage = px.pie(stage_loss, values='Estimated_Loss_EGP', names='Stage', hole=0.4, 
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_stage.update_traces(textposition='inside', textinfo='percent+label')
            fig_stage.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            plot(fig_stage, 180)
            
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            
            prod_loss = qual.groupby('Product_Name').agg(
                Defects=('Rejected_Qty', 'sum'),
                Loss_EGP=('Estimated_Loss_EGP', 'sum')
            ).reset_index().sort_values('Loss_EGP', ascending=False)
            prod_loss['Loss_EGP'] = prod_loss['Loss_EGP'].apply(lambda x: f"{x:,.0f}")
            st.dataframe(prod_loss, use_container_width=True, hide_index=True)

with t2:
    st.markdown("**Ranked Corrective Action Priority List**")
    if not pareto_df.empty:
        action_df = pareto_df.copy()
        
        def assign_priority(cum_pct):
            if cum_pct <= 80.0:
                return "CRITICAL (Pareto 80%)"
            elif cum_pct <= 95.0:
                return "HIGH"
            else:
                return "MONITOR"
                
        def assign_owner(cause):
            c = str(cause).lower()
            if "machine" in c or "calibration" in c: return "Maintenance Eng."
            if "material" in c or "fabric" in c: return "Procurement Dept."
            if "operator" in c or "human" in c: return "Production Supervisor"
            if "print" in c or "ink" in c: return "Printing Facility Manager"
            return "QA Manager"
            
        action_df['Action_Priority'] = action_df['Cumulative_Pct'].apply(assign_priority)
        action_df['Assigned_Owner'] = action_df['Root_Cause'].apply(assign_owner)
        action_df['Estimated_Loss_EGP'] = action_df['Estimated_Loss_EGP'].apply(lambda x: f"{x:,.0f} EGP")
        
        disp_action = action_df[['Root_Cause', 'Estimated_Loss_EGP', 'Action_Priority', 'Assigned_Owner']]
        
        def color_priority(val):
            if 'CRITICAL' in val: return 'color: white; background-color: #EF4444; font-weight: bold;'
            if 'HIGH' in val: return 'color: black; background-color: #FBBF24;'
            return ''
            
        st.dataframe(disp_action.style.map(color_priority, subset=['Action_Priority']), use_container_width=True, hide_index=True)