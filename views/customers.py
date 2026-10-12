import os
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import datetime as dt
from theme import header, kpi, insight

base_path = Path(__file__).resolve().parents[1]
DATA = base_path / "data" if (base_path / "data").exists() else base_path / "DATA"

st.set_page_config(layout="wide", page_title="Customer 360")
header("Customer 360 & Retention Engine", "Analyze customer behavior, loyalty levels, and generate next-best-offer recommendations.", "APP 03")

@st.cache_data(show_spinner=False)
def load_customer_data():
    csv_path = DATA / "Sales_Transactions.csv"
    pq_path = DATA / "Sales_Transactions.parquet"
    
    try:
        if csv_path.exists():
            sales = pd.read_csv(csv_path)
        elif pq_path.exists():
            sales = pd.read_parquet(pq_path)
        else:
            return f"Sales data file not found in directory: {DATA}", None
            
        sales = sales.copy()
        sales['Order_Date'] = pd.to_datetime(sales['Order_Date'])
        
        if 'Net_Sales_EGP' in sales.columns:
            valid_sales = sales[sales['Net_Sales_EGP'] > 0].copy()
            monetary_col = 'Net_Sales_EGP'
        else:
            valid_sales = sales.copy()
            monetary_col = 'Gross_Sales_EGP' if 'Gross_Sales_EGP' in sales.columns else 'Quantity'

        snapshot_date = valid_sales['Order_Date'].max() + dt.timedelta(days=1)
        
        rfm = valid_sales.groupby('Customer_ID').agg(
            Recency=('Order_Date', lambda x: (snapshot_date - x.max()).days),
            Frequency=('Invoice_ID', 'nunique'),
            Monetary=(monetary_col, 'sum')
        ).reset_index()
        
        rfm['R'] = pd.qcut(rfm['Recency'].rank(method='first', ascending=False), q=4, labels=[1, 2, 3, 4])
        rfm['F'] = pd.qcut(rfm['Frequency'].rank(method='first'), q=4, labels=[1, 2, 3, 4])
        rfm['M'] = pd.qcut(rfm['Monetary'].rank(method='first'), q=4, labels=[1, 2, 3, 4])
        
        rfm['RFM_Score'] = rfm[['R', 'F', 'M']].astype(int).sum(axis=1)
        
        def segment_customer(score):
            if score >= 10: return 'VIP'
            elif score >= 8: return 'Loyal'
            elif score >= 6: return 'Potential'
            elif score >= 4: return 'At Risk'
            else: return 'Lost'
            
        rfm['Segment'] = rfm['RFM_Score'].apply(segment_customer)
        
        recs_df = pd.DataFrame()
        basket = valid_sales.groupby(['Invoice_ID', 'Product_Name'])['Quantity'].sum().unstack(fill_value=0)
        basket = (basket > 0).astype(int)
        co_matrix = basket.T.dot(basket)
        np.fill_diagonal(co_matrix.values, 0)
        
        recs = []
        for prod in co_matrix.index:
            if co_matrix.loc[prod].max() > 0:
                top_match = co_matrix.loc[prod].idxmax()
                recs.append({
                    'Purchased Product': prod, 
                    'Next Best Offer': top_match, 
                    'Recommendation Logic': 'Bought Together (Invoice)'
                })
        
        if recs:
            recs_df = pd.DataFrame(recs)
            
        if recs_df.empty or len(recs_df) < 5:
            fallback_recs = []
            if 'Product_Family' in valid_sales.columns:
                valid_sales['Quantity'] = pd.to_numeric(valid_sales['Quantity'], errors='coerce').fillna(0)
                top_per_family = valid_sales.groupby(['Product_Family', 'Product_Name'])['Quantity'].sum().reset_index()
                top_per_family = top_per_family.sort_values(['Product_Family', 'Quantity'], ascending=[True, False])
                
                for prod in valid_sales['Product_Name'].unique():
                    family_series = valid_sales[valid_sales['Product_Name'] == prod]['Product_Family']
                    if not family_series.empty:
                        family = family_series.iloc[0]
                        family_products = top_per_family[(top_per_family['Product_Family'] == family) & (top_per_family['Product_Name'] != prod)]
                        if not family_products.empty:
                            best_alt = family_products.iloc[0]['Product_Name']
                            fallback_recs.append({
                                'Purchased Product': prod,
                                'Next Best Offer': best_alt,
                                'Recommendation Logic': 'Category Top Seller (Affinity)'
                            })
                            
            if fallback_recs:
                recs_df = pd.DataFrame(fallback_recs).head(20)

        return rfm, recs_df
    except Exception as e:
        return str(e), None

rfm_data, recommendations = load_customer_data()

if isinstance(rfm_data, str):
    st.error(f"Error: {rfm_data}")
else:
    tab_profiles, tab_retention = st.tabs(["1. Customer Profiles & Loyalty", "2. Retention & Next Best Offer"])

    with tab_profiles:
        total_customers = len(rfm_data)
        vip_count = len(rfm_data[rfm_data['Segment'] == 'VIP'])
        at_risk_count = len(rfm_data[rfm_data['Segment'] == 'At Risk'])
        avg_clv = rfm_data['Monetary'].mean()
        vip_revenue_share = rfm_data[rfm_data['Segment'] == 'VIP']['Monetary'].sum() / rfm_data['Monetary'].sum()
        
        r1 = st.columns(4)
        r1[0].markdown(kpi("Total Customers", f"{total_customers:,}", "Active in Database", "info"), unsafe_allow_html=True)
        r1[1].markdown(kpi("VIP Customers", f"{vip_count:,}", f"{(vip_count/total_customers)*100:.1f}% of total", "ok"), unsafe_allow_html=True)
        r1[2].markdown(kpi("At-Risk Customers", f"{at_risk_count:,}", "Requires Win-back", "bad"), unsafe_allow_html=True)
        r1[3].markdown(kpi("Avg Customer Value (CLV)", f"{avg_clv/1e3:,.1f}K", "EGP per customer", "info"), unsafe_allow_html=True)
        
        st.write("")
        insight(f"**VIP Customers** make up only **{(vip_count/total_customers)*100:.1f}%** of the base, but they generate **{vip_revenue_share*100:.1f}%** of the total revenue. Focus retention budgets here.")
        st.write("")
        
        col1, col2 = st.columns([1.5, 1])
        
        with col1, st.container(border=True):
            st.markdown("**Customer Segmentation Distribution**")
            seg_counts = rfm_data['Segment'].value_counts().reset_index()
            seg_counts.columns = ['Segment', 'Count']
            fig_pie = px.pie(seg_counts, values='Count', names='Segment', hole=0.4,
                             color='Segment',
                             color_discrete_map={'VIP':'#1D4ED8', 'Loyal':'#3B82F6', 'Potential':'#93C5FD', 'At Risk':'#F59E0B', 'Lost':'#EF4444'})
            fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col2, st.container(border=True):
            st.markdown("**Segment Characteristics (Averages)**")
            seg_summary = rfm_data.groupby('Segment').agg(
                Recency_Days=('Recency', 'mean'),
                Orders=('Frequency', 'mean'),
                Spend_EGP=('Monetary', 'mean')
            ).round(1).reset_index()
            
            seg_summary['Order'] = seg_summary['Segment'].map({'VIP': 1, 'Loyal': 2, 'Potential': 3, 'At Risk': 4, 'Lost': 5})
            seg_summary = seg_summary.sort_values('Order').drop(columns=['Order'])
            st.dataframe(seg_summary, use_container_width=True, hide_index=True)

    with tab_retention:
        st.markdown("### Next Best Offer Engine")
        st.caption("AI-driven product recommendations based on purchase history and category affinity. Use this for cross-selling and bundling.")
        
        if recommendations is not None and not recommendations.empty:
            st.dataframe(recommendations, use_container_width=True, hide_index=True)
        else:
            st.info("No product bundles detected.")
            
        st.markdown("---")
        st.markdown("### Channel & Campaign Targeting")
        st.caption("Strategic actions for marketing teams based on segment health.")
        
        action_plan = pd.DataFrame([
            {"Target Segment": "VIP", "Channel Strategy": "Loyalty Program / Direct Phone", "Next Action": "Exclusive early access to new collections."},
            {"Target Segment": "Loyal", "Channel Strategy": "Email Newsletter", "Next Action": "Upsell using the 'Next Best Offer' recommendations."},
            {"Target Segment": "Potential", "Channel Strategy": "Social Media Retargeting", "Next Action": "Showcase trending products to build habit."},
            {"Target Segment": "At Risk", "Channel Strategy": "SMS / Push Notification", "Next Action": "Send aggressive win-back discount codes."},
        ])
        
        st.dataframe(action_plan, use_container_width=True, hide_index=True)
