import os
import time
import io
from pathlib import Path
import numpy as np, pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st
from sklearn.tree import DecisionTreeRegressor
from theme import header, kpi, pill, insight, plot, PRIMARY, PALETTE

# استدعاء العقل المركزي
try:
    from ai_layer import get_ai_insights
except ImportError:
    try:
        from views.ai_layer import get_ai_insights
    except ImportError:
        get_ai_insights = None

# كود CSS سحري لدعم اللغة العربية وتنسيق الفاتورة والجداول والشات (RTL)
st.markdown("""
<style>
div[data-testid="stChatMessage"] {
    direction: rtl;
    text-align: right;
}
div[data-testid="stChatInput"] {
    direction: rtl;
}
div[data-testid="stChatInput"] textarea {
    direction: rtl;
    text-align: right;
}
.stMarkdown table {
    direction: rtl;
    text-align: right;
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
    margin-bottom: 15px;
}
.stMarkdown th {
    background-color: #f8f9fa;
    color: #1f2937;
    text-align: right !important;
    padding: 10px;
    border: 1px solid #e5e7eb;
}
.stMarkdown td {
    text-align: right !important;
    padding: 10px;
    border: 1px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)

DATA = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
header("Wholesale Deal Desk & Price Guardrail", "Is every wholesale discount earned? Check a quote, set a policy, size the prize.", "APP 08")

@st.cache_data(show_spinner=False)
def load():
    cols = ["Invoice_ID", "Order_Date", "Channel", "Customer_ID", "Product_ID", "Product_Name", "Product_Family", "Quantity",
            "Discount_Pct", "Gross_Sales_EGP", "Net_Sales_EGP", "Estimated_COGS_EGP", "Gross_Profit_EGP"]
    
    csv_path = DATA / "Sales_Transactions.csv"
    pq_path = DATA / "Sales_Transactions.parquet"
    
    try:
        s = pd.read_csv(csv_path, usecols=cols, parse_dates=["Order_Date"])
    except:
        try:
            s = pd.read_parquet(pq_path, columns=cols)
            s['Order_Date'] = pd.to_datetime(s['Order_Date'])
        except:
            st.error("Sales_Transactions data not found! Please ensure your CSV or Parquet file is in the 'data' folder.")
            st.stop()

    w = s[s.Channel == "Wholesale"].copy()
    return s.Net_Sales_EGP.sum(), s.Order_Date.max(), w

def rank_corr(a, b):
    return a.rank().corr(b.rank())

tot_net, end, w = load()
c12 = (end.to_period("M") - 11).to_timestamp(); w12 = w[w.Order_Date >= c12].copy()

# 1. التعديل الأول: اسم التاب الخارجي باللغة الإنجليزية
t1, t2, t3 = st.tabs(["1. The problem: evidence", "2. AI Deal Desk & Policy Optimizer", "3. B2B Auto-Biller"])

with t1:
    bc = w[w.Gross_Profit_EGP <= 0]; bc12 = w12[w12.Gross_Profit_EGP <= 0]
    k = st.columns(6)
    k[0].markdown(kpi("Wholesale share of sales", f"{w.Net_Sales_EGP.sum()/tot_net:.0%}", "net sales, all periods"), unsafe_allow_html=True)
    k[1].markdown(kpi("Average discount", f"{1 - w.Net_Sales_EGP.sum()/w.Gross_Sales_EGP.sum():.1%}", f"range {w.Discount_Pct.min():.0%}–{w.Discount_Pct.max():.0%} by line"), unsafe_allow_html=True)
    k[2].markdown(kpi("Wholesale margin (12m)", f"{w12.Gross_Profit_EGP.sum()/w12.Net_Sales_EGP.sum():.1%}", f"{w12.Gross_Profit_EGP.sum()/1e6:,.1f}M EGP gross profit", "Low", "bad"), unsafe_allow_html=True)
    k[3].markdown(kpi("Lines at or below cost", f"{len(bc):,}", f"{len(bc)/len(w):.1%} of wholesale lines", "Review", "warn"), unsafe_allow_html=True)
    k[4].markdown(kpi("Loss on those lines", f"{bc.Gross_Profit_EGP.sum()/1e6:,.2f}M", f"all periods · {bc12.Gross_Profit_EGP.sum()/1e6:,.2f}M last 12m"), unsafe_allow_html=True)
    k[5].markdown(kpi("Products affected", f"{bc.Product_ID.nunique()}", "of 59 have a below-cost line"), unsafe_allow_html=True)
    st.write("")
    
    rho = w.groupby("Product_ID").apply(lambda d: rank_corr(d.Discount_Pct, d.Quantity), include_groups=False).mean()
    cu = w.groupby("Customer_ID").agg(d=("Discount_Pct", "mean"), q=("Quantity", "sum"))
    insight(f"The wholesale discount is **{w.Discount_Pct.mean():.1%} whatever the order size, customer tier, product family or year**, and it does not buy volume "
            f"(within-product correlation of discount and quantity: {rho:+.3f}). No pricing policy is visible in the data. "
            f"The below-cost lines are the smallest part of the problem ({bc12.Gross_Profit_EGP.sum()/1e6:,.2f}M last 12 months); the big money is the discount level itself.")
    
    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown("**Average wholesale discount by group (flat = no policy)**")
        qb = pd.qcut(w.Quantity, 4, duplicates="drop"); top = set(w.groupby("Customer_ID").Net_Sales_EGP.sum().nlargest(len(cu) // 10).index)
        rows = [("Order size", f"Q{i + 1}", v) for i, v in enumerate(w.groupby(qb, observed=True).Discount_Pct.mean())]
        rows += [("Customer tier", n, v) for n, v in w.groupby(np.where(w.Customer_ID.isin(top), "Top 10%", "Others")).Discount_Pct.mean().items()]
        rows += [("Family", n, v) for n, v in w.groupby("Product_Family").Discount_Pct.mean().items()]
        rows += [("Year", str(n), v) for n, v in w.groupby(w.Order_Date.dt.year).Discount_Pct.mean().items()]
        d = pd.DataFrame(rows, columns=["Group", "Item", "Discount"])
        fig = px.bar(d, x="Item", y="Discount", color="Group", color_discrete_sequence=PALETTE + ["#F59E0B"])
        fig.update_yaxes(tickformat=".0%", range=[0, 0.4]); fig.update_xaxes(tickangle=-35, title_text=""); plot(fig, 300, legend=True)
    with b, st.container(border=True):
        st.markdown("**Gross margin by discount band**")
        bands = pd.cut(w.Discount_Pct, [.275, .30, .32, .34, .36, .385], labels=["28–30%", "30–32%", "32–34%", "34–36%", "36–38%"])
        mb = w.groupby(bands, observed=True).agg(n=("Net_Sales_EGP", "sum"), g=("Gross_Profit_EGP", "sum"), lines=("Invoice_ID", "size")).reset_index().rename(columns={"Discount_Pct": "Band"})
        mb["Margin"] = mb.g / mb.n
        fig = px.bar(mb, x="Band", y="Margin", color_discrete_sequence=[PRIMARY], text=mb.Margin.map("{:.1%}".format)); fig.update_yaxes(tickformat=".0%"); plot(fig, 300)
    
    c1, c2 = st.columns([1.3, 1])
    g = (bc.groupby(["Product_ID", "Product_Name"]).agg(lines=("Invoice_ID", "size"), loss=("Gross_Profit_EGP", "sum")).reset_index().sort_values("loss"))
    tot_l = w.groupby("Product_ID").size(); wm = w.groupby("Product_ID").agg(n=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum"), gr=("Gross_Sales_EGP", "sum"), cg=("Estimated_COGS_EGP", "sum"))
    with c1, st.container(border=True):
        st.markdown("**Products selling below cost in Wholesale (top 8 by loss)**")
        rows = ""
        for r in g.head(8).itertuples():
            share = r.lines / tot_l[r.Product_ID]; zero = 1 - wm.cg[r.Product_ID] / wm.gr[r.Product_ID]
            rows += (f"<tr><td>{r.Product_ID}</td><td>{r.Product_Name[:30]}</td><td>{r.lines:,}</td><td>{pill(f'{share:.0%}', 'bad' if share > .5 else 'warn')}</td>"
                     f"<td>{r.loss/1e3:,.0f}K</td><td>{wm.gp[r.Product_ID]/wm.n[r.Product_ID]:.1%}</td><td>{zero:.0%}</td></tr>")
        st.markdown('<table class="tbl"><tr><th>ID</th><th>PRODUCT</th><th>BELOW-COST LINES</th><th>% OF ITS LINES</th><th>LOSS</th><th>WHOLESALE MARGIN</th><th>MAX DISCOUNT AT COST</th></tr>'
                    f'{rows}</table>', unsafe_allow_html=True)
    with c2, st.container(border=True):
        st.markdown("**Discount distribution (all wholesale lines)**")
        fig = px.histogram(w, x="Discount_Pct", nbins=11, color_discrete_sequence=["#93C5FD"]); fig.update_xaxes(tickformat=".0%", title_text=""); plot(fig, 270)

with t2:
    st.markdown("**AI Deal Desk & Policy Optimizer**")
    st.caption("Determine the optimal discount for any quote and automatically generate pricing policies based on historical data.")
    
    ctrl1, ctrl2, ctrl3 = st.columns([1, 1.5, 1])
    period = ctrl1.selectbox("Training Period", ["Last 3 Months", "Last 6 Months", "Last 12 Months", "All Time"], index=2)
    
    u = w.groupby(["Product_ID", "Product_Name"]).agg(list_u=("Gross_Sales_EGP", "sum"), cogs=("Estimated_COGS_EGP", "sum"), q=("Quantity", "sum")).reset_index()
    u["list_u"] = u.list_u / u.q; u["cogs"] = u.cogs / u.q
    opts = {f"{r.Product_ID} - {r.Product_Name[:38]}": r for r in u.itertuples()}
    
    pick = ctrl2.selectbox("Product", list(opts), index=list(u.Product_ID).index("P048") if "P048" in set(u.Product_ID) else 0)
    qty = ctrl3.number_input("Order Quantity", 1, 5000, 36, 1)
    
    if st.button("Run AI Optimizer", type="primary"):
        with st.spinner("Analyzing data and generating recommendations..."):
            time.sleep(1) 
            
            max_date = w.Order_Date.max()
            if "3" in period:
                start_date = (max_date.to_period("M") - 2).to_timestamp()
            elif "6" in period:
                start_date = (max_date.to_period("M") - 5).to_timestamp()
            elif "12" in period:
                start_date = (max_date.to_period("M") - 11).to_timestamp()
            else:
                start_date = w.Order_Date.min()
            
            w_train = w[w.Order_Date >= start_date].copy()
            
            d_opt = w_train[w_train.Gross_Profit_EGP > 0].copy()
            if len(d_opt) > 0:
                X = d_opt[['Quantity']]; y = d_opt['Discount_Pct']
                dt = DecisionTreeRegressor(max_depth=2, random_state=42)
                dt.fit(X, y)
                
                cap_s = d_opt[d_opt.Quantity <= 24]['Discount_Pct'].quantile(0.25)
                cap_m = d_opt[(d_opt.Quantity > 24) & (d_opt.Quantity <= 50)]['Discount_Pct'].quantile(0.35)
                cap_l = d_opt[d_opt.Quantity > 50]['Discount_Pct'].quantile(0.50)
                cap_s, cap_m, cap_l = [c if pd.notna(c) else v for c, v in zip([cap_s, cap_m, cap_l], [0.28, 0.30, 0.32])]
            else:
                cap_s, cap_m, cap_l = 0.28, 0.30, 0.32
                
            m_min = 0.08 
            p = opts[pick]
            
            if qty <= 24:
                ai_tier_discount = cap_s
            elif qty <= 50:
                ai_tier_discount = cap_m
            else:
                ai_tier_discount = cap_l
                
            guardrail_discount = 1 - p.cogs / ((1 - m_min) * p.list_u)
            final_discount = min(ai_tier_discount, guardrail_discount)
            final_discount = max(0.0, final_discount)
            
            status_color = "bad" if guardrail_discount < 0 else "ok"
            if guardrail_discount < 0: final_discount = 0.0
            
            net_price = p.list_u * (1 - final_discount)
            deal_margin = (net_price - p.cogs) / net_price if net_price > 0 else 0
            
            st.markdown("### AI Pricing Recommendation")
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(kpi("Max Recommended Discount", f"{final_discount*100:.0f}%", f"AI Tier: {ai_tier_discount*100:.0f}%", status_color), unsafe_allow_html=True)
            k2.markdown(kpi("Net Unit Price", f"{net_price:,.0f} EGP", f"Cost: {p.cogs:,.0f} EGP"), unsafe_allow_html=True)
            k3.markdown(kpi("Expected Gross Margin", f"{deal_margin:.1%}", "Profit Margin"), unsafe_allow_html=True)
            k4.markdown(kpi("Total Deal Profit", f"{(net_price - p.cogs)*qty:,.0f} EGP", "Gross Profit"), unsafe_allow_html=True)
            
            if guardrail_discount < ai_tier_discount and guardrail_discount >= 0:
                st.warning(f"Alert: The recommended discount was reduced from {ai_tier_discount*100:.0f}% to {final_discount*100:.0f}% to protect the gross margin of this high-cost product.")
            elif guardrail_discount < 0:
                st.error("Critical Alert: This product is sold at a loss or at cost even without any discounts. No discount is recommended.")
                
            st.write("")
            
            st.markdown("### General Policy & Financial Impact")
            
            def calculate_impact(d, caps, mmin):
                tier = np.where(d.Quantity <= 24, caps[0], np.where(d.Quantity <= 50, caps[1], caps[2]))
                floor = np.clip(1 - d.Estimated_COGS_EGP / ((1 - mmin) * d.Gross_Sales_EGP), 0, 1)
                new = np.minimum(d.Discount_Pct, np.minimum(tier, floor))
                return d.Gross_Sales_EGP * (1 - new), d.Gross_Sales_EGP * (1 - new) - d.Estimated_COGS_EGP

            net_new, gp_new = calculate_impact(w_train, (cap_s, cap_m, cap_l), m_min)
            gp0, net0 = w_train.Gross_Profit_EGP.sum(), w_train.Net_Sales_EGP.sum()
            d_gp = gp_new.sum() - gp0
            
            c1, c2 = st.columns([1.2, 1])
            with c1, st.container(border=True):
                st.markdown("**Extracted Rules (Based on selected period):**")
                st.markdown(f"- **Rule 1 (Small Orders 1-24 units):** Max Discount = **{cap_s*100:.0f}%**")
                st.markdown(f"- **Rule 2 (Medium Orders 25-50 units):** Max Discount = **{cap_m*100:.0f}%**")
                st.markdown(f"- **Rule 3 (Large Orders 50+ units):** Max Discount = **{cap_l*100:.0f}%**")
                st.markdown(f"- **Safety Guardrail:** Never drop Gross Margin below **{m_min*100:.0f}%**.")
            
            with c2, st.container(border=True):
                st.markdown("**Simulation Impact:**")
                i1, i2 = st.columns(2)
                i1.markdown(kpi("Recovered Profit", f"+ {d_gp/1e6:,.2f}M EGP", "Simulation output", "ok"), unsafe_allow_html=True)
                i2.markdown(kpi("New Margin", f"{gp_new.sum()/net_new.sum():.1%}", f"Improved from {gp0/net0:.1%}", "info"), unsafe_allow_html=True)
                st.markdown(f"*Applying this policy retroactively to the selected period would have protected the company from below-cost sales and saved this amount.*")

with t3:
    # 2. التعديل الثاني: العنوان الداخلي بالعربي
    st.markdown("### بوابة فواتير الجملة الآلية")
    
    if get_ai_insights is None:
        st.error(" برجاء التأكد من وجود ملف `ai_layer.py` لعمل النظام.")
    else:
        if "latest_query" not in st.session_state:
            st.session_state.latest_query = None
            st.session_state.latest_response = None

        if prompt := st.chat_input("اكتب طلب التاجر هنا (الكميات وأكواد المنتجات المطلوبة) ..."):
            st.session_state.latest_query = prompt
            
            with st.spinner("جاري فحص المخزون وإصدار الفاتورة المبدئية..."):
                u = w.groupby(["Product_ID", "Product_Name"]).agg(list_u=("Gross_Sales_EGP", "sum"), cogs=("Estimated_COGS_EGP", "sum"), q=("Quantity", "sum")).reset_index()
                u["list_u"] = u.list_u / u.q
                
                context_lines = []
                for r in u.dropna().itertuples():
                    context_lines.append(f"كود {r.Product_ID} ({r.Product_Name}): السعر الأساسي {r.list_u:.2f} ج.م")
                
                b2b_context = "قائمة أسعار الجملة المتاحة للرد على العميل:\n" + "\n".join(context_lines)
                
                response = get_ai_insights(context_data=b2b_context, user_query=prompt, role_type="B2B Sales Rep")
                st.session_state.latest_response = response
                
                # 3. التعديل الثالث: Decision Log (Invoice Log)
                log_path = DATA / "B2B_Invoice_Log.csv"
                new_log = pd.DataFrame({
                    "Timestamp": [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")],
                    "Trader_Request": [prompt],
                    "AI_Invoice": [response]
                })
                try:
                    if log_path.exists():
                        new_log.to_csv(log_path, mode='a', header=False, index=False, encoding='utf-8-sig')
                    else:
                        new_log.to_csv(log_path, index=False, encoding='utf-8-sig')
                except Exception as e:
                    pass # تخطي في حالة خطأ الحفظ حتى لا يزعج المستخدم

        if st.session_state.latest_query:
            with st.chat_message("user"):
                st.markdown(st.session_state.latest_query)
            
            with st.chat_message("assistant"):
                st.markdown(st.session_state.latest_response)
                
                st.write("") 
                
                # 4. التعديل الرابع: تحويل الفاتورة لصيغة CSV (Excel)
                def extract_table(md_text):
                    lines = [line.strip() for line in md_text.split('\n') if '|' in line]
                    if not lines or len(lines) < 2: return None
                    data_lines = [line for line in lines if not all(c in '| -' for c in line)]
                    if not data_lines or len(data_lines) < 1: return None
                    
                    try:
                        headers = [col.strip() for col in data_lines[0].split('|')[1:-1]]
                        rows = []
                        for line in data_lines[1:]:
                            cols = [col.strip() for col in line.split('|')[1:-1]]
                            rows.append(cols)
                        return pd.DataFrame(rows, columns=headers)
                    except:
                        return None
                
                df_invoice = extract_table(st.session_state.latest_response)
                
                if df_invoice is not None:
                    # تحويل الجدول إلى CSV متوافق مع الإكسيل
                    csv_data = df_invoice.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label=" تحميل الفاتورة (Excel/CSV)",
                        data=csv_data,
                        file_name=f"Invoice_{int(time.time())}.csv",
                        mime="text/csv",
                        type="primary"
                    )
                else:
                    # في حالة فشل التحويل نرجع للنص العادي كبديل
                    download_data = "\ufeff" + st.session_state.latest_response
                    st.download_button(
                        label="📥 تحميل الفاتورة",
                        data=download_data,
                        file_name=f"Invoice_{int(time.time())}.txt",
                        mime="text/plain",
                        type="primary"
                    )
        else:
            with st.chat_message("assistant"):
                st.markdown("أهلاً بك. أدخل الكميات والأكواد المطلوبة لإصدار الفاتورة.")
