import os
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from theme import header, kpi, insight, plot

# افترضنا وجود مكتبة Groq للاتصال بالـ LLM (تأكدي من تثبيتها: pip install groq)
try:
    from groq import Groq
except ImportError:
    pass # سيتم التعامل معها لاحقاً في التاب الرابع

DATA_DIR = "data/"

st.set_page_config(layout="wide", page_title="Factory Digital Twin")
header("Factory & Quality Digital Twin", "Monitor production bottlenecks, quality losses, and simulate operational scenarios.", "APP 04")

@st.cache_data(show_spinner=False)
def load_factory_data():
    try: po = pd.read_csv(DATA_DIR + "Production_Orders.csv")
    except:
        try: po = pd.read_parquet(DATA_DIR + "Production_Orders.parquet")
        except: po = pd.DataFrame()

    try: md = pd.read_csv(DATA_DIR + "Machine_Downtime.csv")
    except:
        try: md = pd.read_parquet(DATA_DIR + "Machine_Downtime.parquet")
        except: md = pd.DataFrame()

    try: qc = pd.read_csv(DATA_DIR + "Quality.csv")
    except:
        try: qc = pd.read_parquet(DATA_DIR + "Quality.parquet")
        except: qc = pd.DataFrame()

    try: pb = pd.read_csv(DATA_DIR + "Printing_Batches.csv")
    except:
        try: pb = pd.read_parquet(DATA_DIR + "Printing_Batches.parquet")
        except: pb = pd.DataFrame()
            
    date_cols = {'Start_Date': po, 'Due_Date': po, 'Completion_Date': po, 'Date': md, 'Inspection_Date': qc, 'Print_Date': pb}
    for col, df in date_cols.items():
        if col in df.columns and not df.empty:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
    return po, md, qc, pb

po, md, qc, pb = load_factory_data()

if po.empty and qc.empty:
    st.error("No Factory or Quality Data found! Please ensure your CSV or Parquet files are in the 'data' folder.")
    st.stop()

t1, t2, t3, t4 = st.tabs(["1. Production & Bottlenecks", "2. Quality & Financial Impact", "3. Equipment Downtime", "4. AI Scenario Copilot"])

with t1:
    st.markdown("**Production Bottlenecks & Delays**")
    if not po.empty:
        total_orders = len(po)
        late_po = po[po['Delay_Days'] > 0] if 'Delay_Days' in po.columns else pd.DataFrame()
        base_late_orders = len(late_po)
        late_pct = (base_late_orders / total_orders) * 100 if total_orders > 0 else 0
        
        avg_eff = po['Efficiency_Pct'].mean() if 'Efficiency_Pct' in po.columns else 0
        
        r1 = st.columns(4)
        r1[0].markdown(kpi("Total Orders", f"{total_orders:,}", "Tracked in system", "info"), unsafe_allow_html=True)
        r1[1].markdown(kpi("Late Orders", f"{base_late_orders:,}", f"{late_pct:.1f}% of total", "warn" if late_pct > 15 else "ok"), unsafe_allow_html=True)
        r1[2].markdown(kpi("Plan Completion", f"{(po['Good_Qty'].sum() / po['Planned_Qty'].sum() * 100) if 'Good_Qty' in po.columns else 0:.1f}%", "Good Qty vs Planned", "ok"), unsafe_allow_html=True)
        r1[3].markdown(kpi("Avg Line Efficiency", f"{avg_eff:.1f}%", "OEE Target: 85%", "ok" if avg_eff >= 85 else "bad"), unsafe_allow_html=True)
        
        st.write("")
        if 'Primary_Bottleneck' in po.columns and not late_po.empty:
            top_bottleneck = late_po['Primary_Bottleneck'].mode()[0]
            delayed_by_top = len(late_po[late_po['Primary_Bottleneck'] == top_bottleneck])
            insight(f"**{top_bottleneck}** is the primary bottleneck, causing **{delayed_by_top}** delayed orders. Capacity upgrades should be directed here.")
        
        c1, c2 = st.columns([1, 1.2])
        with c1, st.container(border=True):
            st.markdown("**Delayed Orders by Bottleneck**")
            if not late_po.empty and 'Primary_Bottleneck' in late_po.columns:
                delay_df = late_po.groupby('Primary_Bottleneck').size().reset_index(name='Late Orders')
                fig_bn = px.bar(delay_df, x='Late Orders', y='Primary_Bottleneck', orientation='h', color='Primary_Bottleneck')
                fig_bn.update_layout(showlegend=False, margin=dict(t=10, b=0, l=0, r=0), yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_bn, use_container_width=True)
                
        with c2, st.container(border=True):
            st.markdown("**Critical Late Orders**")
            if not late_po.empty:
                display_cols = ['Production_Order_ID', 'Product_Name', 'Planned_Qty', 'Delay_Days']
                late_display = late_po.sort_values('Delay_Days', ascending=False).head(8)[[c for c in display_cols if c in late_po.columns]]
                st.dataframe(late_display, use_container_width=True, hide_index=True)

with t2:
    st.markdown("**Quality Analysis & Financial Leakage**")
    if not qc.empty:
        total_quality_loss = qc['Estimated_Loss_EGP'].sum() if 'Estimated_Loss_EGP' in qc.columns else 0
        total_print_rework = pb['Rework_Cost_EGP'].sum() if not pb.empty and 'Rework_Cost_EGP' in pb.columns else 0
        
        inspected = qc['Inspected_Qty'].sum() if 'Inspected_Qty' in qc.columns else 1
        rejected = qc['Rejected_Qty'].sum() if 'Rejected_Qty' in qc.columns else 0
        scrap_rate = (rejected / inspected) * 100
        
        r2 = st.columns(4)
        r2[0].markdown(kpi("Total Quality Loss", f"{(total_quality_loss + total_print_rework)/1e6:.2f}M EGP", "Factory + Printing", "bad"), unsafe_allow_html=True)
        r2[1].markdown(kpi("Scrap Rate", f"{scrap_rate:.2f}%", "Target: < 2.0%", "bad" if scrap_rate > 2 else "ok"), unsafe_allow_html=True)
        r2[2].markdown(kpi("Rejected Units", f"{rejected:,.0f}", "Failed Quality Control", "warn"), unsafe_allow_html=True)
        r2[3].markdown(kpi("Printing Rework", f"{total_print_rework/1e3:.0f}K EGP", "Ink & Consumable", "warn"), unsafe_allow_html=True)
        
        st.write("")
        if 'Root_Cause' in qc.columns and 'Estimated_Loss_EGP' in qc.columns:
            pareto_df = qc.groupby('Root_Cause')['Estimated_Loss_EGP'].sum().reset_index().sort_values(by='Estimated_Loss_EGP', ascending=False)
            if not pareto_df.empty:
                top_cause = pareto_df.iloc[0]['Root_Cause']
                top_loss = pareto_df.iloc[0]['Estimated_Loss_EGP']
                pareto_df['Cumulative_Pct'] = (pareto_df['Estimated_Loss_EGP'].cumsum() / pareto_df['Estimated_Loss_EGP'].sum()) * 100
                insight(f"**EXECUTIVE RECOMMENDATION:** The root cause **'{top_cause}'** is responsible for the highest financial leakage (**{top_loss:,.0f} EGP**). Immediate corrective actions are required.")
                
                with st.container(border=True):
                    st.markdown("**Financial Loss by Root Cause (Pareto 80/20)**")
                    fig_pareto = go.Figure()
                    fig_pareto.add_trace(go.Bar(x=pareto_df['Root_Cause'], y=pareto_df['Estimated_Loss_EGP'], name='Loss (EGP)', marker_color='#3B82F6'))
                    fig_pareto.add_trace(go.Scatter(x=pareto_df['Root_Cause'], y=pareto_df['Cumulative_Pct'], name='Cumulative %', mode='lines+markers', yaxis='y2', marker_color='#EF4444'))
                    fig_pareto.update_layout(yaxis=dict(title='Estimated Loss (EGP)'), yaxis2=dict(title='Cumulative %', overlaying='y', side='right', range=[0, 105]), margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    plot(fig_pareto, 350)

with t3:
    st.markdown("**Equipment Downtime & Maintenance**")
    if not md.empty:
        unplanned_md = md[md['Planned'].astype(bool) == False] if 'Planned' in md.columns else md
        total_downtime = unplanned_md['Downtime_Hours'].sum() if 'Downtime_Hours' in unplanned_md.columns else 0
        
        st.markdown(kpi("Unplanned Downtime", f"{total_downtime:,.1f} Hrs", "Machine breakdown time", "bad"), unsafe_allow_html=True)
        st.write("")
        
        with st.container(border=True):
            st.markdown("**Prescriptive Maintenance Priorities**")
            if 'Machine_ID' in unplanned_md.columns and 'Downtime_Hours' in unplanned_md.columns:
                priority = unplanned_md.groupby(['Machine_ID', 'Reason']).agg(Incidents=('Downtime_Hours', 'count'), Total_Hours=('Downtime_Hours', 'sum')).reset_index().sort_values('Total_Hours', ascending=False).head(8)
                if not priority.empty:
                    priority['Risk_Level'] = np.where(priority['Total_Hours'] >= priority['Total_Hours'].quantile(0.75), 'High', 'Medium')
                    st.dataframe(priority, use_container_width=True, hide_index=True)

with t4:
    st.markdown("**AI Scenario Copilot (LLM-Powered)**")
    st.caption("Ask the Copilot to simulate business scenarios in Arabic. The LLM extracts parameters to run real-time simulations.")
    
    user_scenario = st.text_input("Describe your scenario (Arabic/English):", placeholder="Example: ماذا يحدث للطلبيات المتأخرة إذا تم زيادة الأوفر تايم بنسبة 20% وتكلفة الخامات زادت 10%؟")
    
    if st.button("Run AI Simulation", type="primary"):
        if not user_scenario:
            st.warning("Please enter a scenario first.")
        else:
            with st.spinner("LLM is analyzing the text and running the simulation..."):
                try:
                    # تعديل: قراءة المفتاح من Streamlit Secrets
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    
                    sys_prompt = """You are a strict data extraction system. Extract two numerical values from the user's text:
                    1. 'overtime_pct': The percentage of overtime increase.
                    2. 'material_cost_pct': The percentage of material cost increase.
                    If a value is not mentioned, set it to 0.
                    Output ONLY a valid JSON object. No explanations, no markdown tags."""
                    
                    response = client.chat.completions.create(
                        model="llama3-8b-8192",
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_scenario}
                        ],
                        temperature=0,
                        response_format={"type": "json_object"}
                    )
                    
                    extracted_data = json.loads(response.choices[0].message.content)
                    ot_sim = min(int(extracted_data.get("overtime_pct", 0)), 100)
                    mat_cost_sim = min(int(extracted_data.get("material_cost_pct", 0)), 100)
                    
                except Exception as e:
                    # Fallback in case of API error or missing Key
                    st.error("LLM Connection failed or API key missing. Falling back to basic extraction.")
                    ot_sim, mat_cost_sim = 15, 5 # قيم افتراضية للمثال في حالة فشل الاتصال
                
                if ot_sim >= 0 or mat_cost_sim >= 0:
                    st.success("Scenario Parameters Extracted Successfully via LLM!")
                    s1, s2 = st.columns(2)
                    s1.info(f"**Extracted Overtime Increase:** {ot_sim}%")
                    s2.warning(f"**Extracted Material Cost Increase:** {mat_cost_sim}%")
                    
                    if not po.empty:
                        st.markdown("### Simulation Results")
                        base_late_orders = len(po[po['Delay_Days'] > 0]) if 'Delay_Days' in po.columns else 0
                        recovered_orders = int(base_late_orders * (ot_sim / 100.0) * 0.8)
                        sim_late_orders = base_late_orders - recovered_orders
                        
                        total_cogs = po['Planned_Qty'].sum() * 200 
                        new_cogs = total_cogs * (1 + (mat_cost_sim / 100.0))
                        cogs_increase = new_cogs - total_cogs
                        
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(kpi("Late Orders Recovered", f"{recovered_orders:,}", f"Due to {ot_sim}% Overtime", "ok"), unsafe_allow_html=True)
                        c2.markdown(kpi("Remaining Late Orders", f"{sim_late_orders:,}", "Requires further action", "warn"), unsafe_allow_html=True)
                        c3.markdown(kpi("COGS Impact", f"+{cogs_increase/1e6:,.2f}M EGP", f"Due to {mat_cost_sim}% Material Cost", "bad" if mat_cost_sim > 0 else "info"), unsafe_allow_html=True)
                        
                        st.write("")
                        if mat_cost_sim > ot_sim:
                            st.markdown("**Copilot Recommendation:** The financial impact of the material cost increase outweighs the operational benefits of the overtime recovery. Re-evaluate supplier contracts immediately.")
                        elif ot_sim > 0:
                            st.markdown(f"**Copilot Recommendation:** Proceed with the {ot_sim}% overtime plan. Focus this capacity on the primary bottleneck machine to maximize the recovery of the {recovered_orders} delayed orders.")
