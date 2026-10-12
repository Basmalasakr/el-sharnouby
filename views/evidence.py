import pandas as pd
import streamlit as st
from theme import header

header("Technical Appendix", "Data modeling notes, cleansing log, and core assumptions.", "APPENDIX")

t1, t2, t3 = st.tabs(["1. Data Architecture", "2. Cleansing & Fixes", "3. Model Parameters"])

with t1:
    st.markdown("### ERD & Relationships")
    st.markdown("""
    The dashboard runs on a star-schema-like model linking 6 core operational tables via standard keys (`Product_ID`, `Location_ID`, `Invoice_ID`).
    * **Sales & Commercial:** `Sales_Transactions` - `Customers` 
    * **Supply Chain:** `Inventory_History` - `Sales_Transactions` (Joined to calculate days of cover & stockout costs)
    * **Factory:** `Production_Orders` - `Machine_Downtime` - `Quality` (Linked via batch IDs and timestamps)
    """)
    
    st.markdown("### Dictionary Snapshot")
    dict_data = {
        "Table": ["Sales_Transactions", "Inventory_History", "Quality", "Production_Orders", "Printing_Batches"],
        "Grain": ["Invoice Line", "Monthly Snapshot", "Defect Event", "Batch", "Machine Run"],
        "Key Metrics Calculated": ["Net Sales, Estimated COGS, Gross Margin", "Stock Value, Lost Sales due to Stockouts", "Scrap Rate, Financial Loss by Defect", "OEE, Delay Days, Bottleneck count", "Rework Cost, Reprint Qty"],
        "Used In": ["Control Tower, Final Mission", "Smart Inventory", "Factory Twin (Quality Tab)", "Factory Twin (Production Tab)", "Factory Twin (Equipment Tab)"]
    }
    st.dataframe(pd.DataFrame(dict_data), use_container_width=True, hide_index=True)

with t2:
    st.markdown("### Data Cleansing Log")
    st.info("Notes on data issues found during ETL and the applied workarounds.")
    
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**1. Margin Calculation Override**")
        st.markdown("""
        * **Issue:** Relying on standard `Component_Cost` (BOM) for profitability showed inflated margins because it ignored operational waste and freight.
        * **Fix:** Forced all financial models to use `Estimated_COGS_EGP` directly from sales data as the single source of truth for pricing floors.
        """)
        
        st.markdown("**2. Inventory SKU Orphans**")
        st.markdown("""
        * **Issue:** Several raw material SKUs in the warehouse logs had no matching `Product_ID` in the master catalog.
        * **Fix:** Rolled up inventory metrics to the `Product_Name` level to prevent stock value leakage.
        """)
        
    with c2, st.container(border=True):
        st.markdown("**3. Wholesale Discount Flatlining**")
        st.markdown("""
        * **Issue:** The `Discount_Pct` column for wholesale showed a highly unnatural flat distribution (~32.6% average) regardless of tier or volume. 
        * **Fix:** Treated this as a business process failure (lack of pricing matrix) rather than a data error. The Final Mission (Deal Desk) was built specifically to overwrite this behavior.
        """)

        st.markdown("**4. Downtime Flagging**")
        st.markdown("""
        * **Issue:** The `Planned` maintenance column in Factory data had mixed boolean/string formats (Yes, 1, true, False).
        * **Fix:** Standardized to strict booleans during load to ensure unplanned downtime KPIs are accurate.
        """)

with t3:
    st.markdown("### Hardcoded Parameters & Assumptions")
    
    st.markdown("#### Deal Desk Simulator (Final Mission)")
    st.markdown("""
    * **Elasticity:** The historical data showed zero correlation between volume and discount size (rho = -0.002).
    * **Stress Test:** To keep the business case conservative, we hardcoded a **10% strict volume loss** penalty on any invoice where the new policy reduces the historical discount.
    * **Safety Net:** The model proves profitability holds until volume churn hits 48%.
    """)

    st.markdown("#### Smart Inventory & Forecasting")
    st.markdown("""
    * **Overstock Definition:** Hardcoded at **180 Days of Cover**. Anything above this is flagged for liquidation or inter-branch transfer.
    * **Demand Forecast:** The 30/60/90 day forecast uses a blended model (50% 3-month moving average + 50% seasonal lag from T-12 months) to handle both trends and seasonality.
    * **Stockout Cost:** Calculated as `Avg_Daily_Sales_90D` x `Stockout_Days_In_Month` x `Net_Unit_Price`.
    """)
    
    st.markdown("#### Factory Twin")
    st.markdown("""
    * **Overtime Simulation:** Assumed an 80% recovery efficiency. Example: simulating a 10% increase in overtime capacity mathematically recovers 8% of the delayed production orders.
    * **Pareto Logic:** Quality defects are dynamically ranked; the system automatically isolates the top defects contributing to 80% of the financial loss for root-cause analysis.
    """)