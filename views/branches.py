import os
import pandas as pd
import plotly.express as px
import streamlit as st
from theme import header, kpi, insight, plot

DATA_DIR = "data/"
st.set_page_config(layout="wide", page_title="Branch Expansion")
header("Branch Intelligence & Expansion", "Which branch wins and where should the next one open?", "APP 06")

EGYPT_COORDS = {
    "Cairo": {"lat": 30.0444, "lon": 31.2357},
    "Alexandria": {"lat": 31.2001, "lon": 29.9187},
    "Giza": {"lat": 30.0131, "lon": 31.2089},
    "Dakahlia": {"lat": 31.0364, "lon": 31.3807},
    "Mansoura": {"lat": 31.0364, "lon": 31.3807},
    "Red Sea": {"lat": 27.2579, "lon": 33.8116},
    "Sharqia": {"lat": 30.5877, "lon": 31.5020},
    "Gharbia": {"lat": 30.8754, "lon": 31.0335},
    "Monufia": {"lat": 30.5972, "lon": 30.9876},
    "Qalyubia": {"lat": 30.4069, "lon": 31.2205},
    "Port Said": {"lat": 31.2653, "lon": 32.3019},
    "Suez": {"lat": 29.9668, "lon": 32.5498},
    "Ismailia": {"lat": 30.5965, "lon": 32.2715},
    "Faiyum": {"lat": 29.3084, "lon": 30.8428},
    "Beni Suef": {"lat": 29.0661, "lon": 31.0994},
    "Minya": {"lat": 28.0871, "lon": 30.7618},
    "Asyut": {"lat": 27.1810, "lon": 31.1837},
    "Sohag": {"lat": 26.5591, "lon": 31.6957},
    "Qena": {"lat": 26.1551, "lon": 32.7160},
    "Luxor": {"lat": 25.6872, "lon": 32.6396},
    "Aswan": {"lat": 24.0889, "lon": 32.8998},
    "Sidi Bishr": {"lat": 31.2653, "lon": 29.9916},
}

@st.cache_data(show_spinner=False)
def load_expansion_data():
    try:
        sales = pd.read_csv(DATA_DIR + "Sales_Transactions.csv")
    except:
        try:
            sales = pd.read_parquet(DATA_DIR + "Sales_Transactions.parquet")
        except:
            sales = pd.DataFrame()
            
    try:
        locs = pd.read_csv(DATA_DIR + "Locations.csv")
    except:
        locs = pd.DataFrame()
        
    return sales, locs

sales, locs = load_expansion_data()

if sales.empty:
    st.error("Sales data is required for this module.")
    st.stop()

sales_net = sales['Net_Sales_EGP'] if 'Net_Sales_EGP' in sales.columns else sales['Gross_Sales_EGP']
sales['Revenue'] = sales_net

retail_sales = sales[sales['Channel'].str.contains("Retail|Store", case=False, na=False)].copy() if 'Channel' in sales.columns else sales.copy()

if 'Location_Name' in retail_sales.columns:
    branch_perf = retail_sales.groupby('Location_Name').agg(
        Revenue=('Revenue', 'sum'),
        Orders=('Row_ID', 'count')
    ).reset_index().sort_values('Revenue', ascending=False)
    
    branch_perf['lat'] = branch_perf['Location_Name'].apply(lambda x: next((v['lat'] for k, v in EGYPT_COORDS.items() if k.lower() in str(x).lower()), 30.0444))
    branch_perf['lon'] = branch_perf['Location_Name'].apply(lambda x: next((v['lon'] for k, v in EGYPT_COORDS.items() if k.lower() in str(x).lower()), 31.2357))
    branch_perf['Type'] = 'Existing Retail'
else:
    branch_perf = pd.DataFrame()

online_sales = sales[sales['Channel'].str.contains("Online|Web|App", case=False, na=False)].copy() if 'Channel' in sales.columns else pd.DataFrame()

if not online_sales.empty and 'Customer_Governorate' in online_sales.columns:
    online_perf = online_sales.groupby('Customer_Governorate').agg(
        Online_Revenue=('Revenue', 'sum'),
        Online_Orders=('Row_ID', 'count')
    ).reset_index()
    
    existing_govs = []
    if not locs.empty and 'Governorate' in locs.columns:
        existing_govs = locs[locs['Channel'].str.contains("Retail", na=False)]['Governorate'].dropna().unique().tolist()
    elif not branch_perf.empty:
        existing_govs = [k for k in EGYPT_COORDS.keys() if any(k.lower() in str(x).lower() for x in branch_perf['Location_Name'])]

    untapped_markets = online_perf[~online_perf['Customer_Governorate'].isin(existing_govs)].sort_values('Online_Revenue', ascending=False)
    
    if not untapped_markets.empty:
        top_recommendation = untapped_markets.iloc[0]
        rec_gov = top_recommendation['Customer_Governorate']
        rec_rev = top_recommendation['Online_Revenue']
        rec_orders = top_recommendation['Online_Orders']
        
        rec_lat = EGYPT_COORDS.get(rec_gov, EGYPT_COORDS.get("Cairo"))['lat']
        rec_lon = EGYPT_COORDS.get(rec_gov, EGYPT_COORDS.get("Cairo"))['lon']
        rec_df = pd.DataFrame({
            'Location_Name': [f"RECOMMENDED: {rec_gov}"],
            'Revenue': [rec_rev],
            'Orders': [rec_orders],
            'lat': [rec_lat],
            'lon': [rec_lon],
            'Type': ['Potential Expansion']
        })
        map_data = pd.concat([branch_perf, rec_df], ignore_index=True)
    else:
        map_data = branch_perf
        rec_gov = None
else:
    map_data = branch_perf
    rec_gov = None

st.markdown("<br>", unsafe_allow_html=True)

if rec_gov:
    with st.container(border=True):
        st.markdown(f"**EXECUTIVE RECOMMENDATION:** Based on cross-channel analytics, **{rec_gov}** generates **{rec_rev/1e6:,.1f}M EGP** in online revenue across **{rec_orders:,}** transactions, yet has **0 retail locations**. Establishing the next physical branch here leverages an existing, high-value customer base for guaranteed foot traffic.")

m1, m2 = st.columns([2, 1])

with m1, st.container(border=True):
    st.markdown("**Retail Footprint & Expansion Radar (Omnichannel)**")
    if not map_data.empty:
        try:
            fig_map = px.scatter_map(
                map_data, 
                lat="lat", lon="lon", 
                size="Revenue", 
                color="Type",
                color_discrete_map={"Existing Retail": "#3B82F6", "Potential Expansion": "#EF4444"},
                hover_name="Location_Name", 
                hover_data={"lat": False, "lon": False, "Revenue": ":,.0f", "Type": False},
                zoom=5.5, 
                center={"lat": 29.0, "lon": 31.0},
                map_style="carto-darkmatter"
            )
        except AttributeError:
            fig_map = px.scatter_geo(
                map_data, 
                lat="lat", lon="lon", 
                size="Revenue", 
                color="Type",
                color_discrete_map={"Existing Retail": "#3B82F6", "Potential Expansion": "#EF4444"},
                hover_name="Location_Name",
                hover_data={"lat": False, "lon": False, "Revenue": ":,.0f", "Type": False}
            )
            fig_map.update_geos(fitbounds="locations", showland=True, landcolor="#222222", showcountries=True)

        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.warning("Insufficient location data to plot the map.")

with m2:
    st.markdown("**Branch Performance Leaderboard**")
    if not branch_perf.empty:
        disp_branch = branch_perf[['Location_Name', 'Revenue', 'Orders']].copy()
        disp_branch['Revenue'] = disp_branch['Revenue'].apply(lambda x: f"{x/1e6:,.1f}M")
        st.dataframe(disp_branch, use_container_width=True, hide_index=True)
    
    if not online_sales.empty:
        st.markdown("**Untapped Markets (High Online, No Retail)**")
        if not untapped_markets.empty:
            disp_untapped = untapped_markets.head(4).copy()
            disp_untapped['Online_Revenue'] = disp_untapped['Online_Revenue'].apply(lambda x: f"{x/1e6:,.1f}M")
            st.dataframe(disp_untapped.rename(columns={"Customer_Governorate": "Governorate", "Online_Revenue": "Online Rev"}), use_container_width=True, hide_index=True)