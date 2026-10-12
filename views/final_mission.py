import os
from pathlib import Path
import numpy as np, pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st
from theme import header, kpi, pill, insight, plot, PRIMARY, PALETTE

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
            st.error("⚠️ Sales_Transactions data not found! Please ensure your CSV or Parquet file is in the 'data' folder.")
            st.stop()

    w = s[s.Channel == "Wholesale"].copy()
    return s.Net_Sales_EGP.sum(), s.Order_Date.max(), w

def rank_corr(a, b):
    return a.rank().corr(b.rank())

tot_net, end, w = load()
c12 = (end.to_period("M") - 11).to_timestamp(); w12 = w[w.Order_Date >= c12].copy()

t1, t2, t3 = st.tabs(["1. The problem: evidence", "2. Deal checker (prototype)", "3. Policy & business case"])

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
        st.caption(f"Within a customer the discount varies by {w.groupby('Customer_ID').Discount_Pct.std().mean()*100:.1f} points, almost as much as across all lines ({w.Discount_Pct.std()*100:.1f}): "
                   f"no customer-specific price agreements either. Customers with higher average discount do not buy more (rank correlation {rank_corr(cu.d, cu.q):+.2f}).")
    with b, st.container(border=True):
        st.markdown("**Gross margin by discount band**")
        bands = pd.cut(w.Discount_Pct, [.275, .30, .32, .34, .36, .385], labels=["28–30%", "30–32%", "32–34%", "34–36%", "36–38%"])
        mb = w.groupby(bands, observed=True).agg(n=("Net_Sales_EGP", "sum"), g=("Gross_Profit_EGP", "sum"), lines=("Invoice_ID", "size")).reset_index().rename(columns={"Discount_Pct": "Band"})
        mb["Margin"] = mb.g / mb.n
        fig = px.bar(mb, x="Band", y="Margin", color_discrete_sequence=[PRIMARY], text=mb.Margin.map("{:.1%}".format)); fig.update_yaxes(tickformat=".0%"); plot(fig, 300)
        st.caption("Every 2 points of extra discount costs about 3 points of margin, with no extra volume in return.")
    
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
        t5 = g.head(5); st.caption(f"The top 5 products hold {t5.lines.sum()/g.lines.sum():.0%} of below-cost lines and {t5.loss.sum()/g.loss.sum():.0%} of the loss (EGP). 'Max discount at cost' = the discount at which gross profit is zero.")
    with c2, st.container(border=True):
        st.markdown("**Discount distribution (all wholesale lines)**")
        fig = px.histogram(w, x="Discount_Pct", nbins=11, color_discrete_sequence=["#93C5FD"]); fig.update_xaxes(tickformat=".0%", title_text=""); plot(fig, 270)
        st.caption("Roughly uniform between 28% and 38%: the discount looks like a draw, not a decision.")

with t2:
    st.markdown("**Quote checker: what happens to the margin if we give this discount?**")
    s1, s2 = st.columns(2)
    green_m = s1.slider("Green: gross margin at least (%)", 5, 25, 12, 1) / 100
    red_m = s2.slider("Red: gross margin below (%)", -10, 10, 0, 1) / 100
    if red_m >= green_m:
        st.warning("The red threshold must be below green: using green minus 1 point for red.")
        red_m = green_m - 0.01
    st.caption("Defaults: green equals today's wholesale margin; red is selling below cost. Both are assumptions to agree with Sales and Finance. "
               "Cost basis = estimated COGS per unit from the sales data (full cost); raw-material (BOM) cost is only about 30% of the price, "
               "so using it as a floor would approve almost any deal.")
    
    u = w12.groupby(["Product_ID", "Product_Name"]).agg(list_u=("Gross_Sales_EGP", "sum"), cogs=("Estimated_COGS_EGP", "sum"), q=("Quantity", "sum"),
                                                         today=("Discount_Pct", "mean")).reset_index()
    u["list_u"] = u.list_u / u.q; u["cogs"] = u.cogs / u.q
    opts = {f"{r.Product_ID} - {r.Product_Name[:38]}": r for r in u.itertuples()}
    x1, x2, x3 = st.columns([2, 1, 1.4])
    pick = x1.selectbox("Product", list(opts), index=list(u.Product_ID).index("P048") if "P048" in set(u.Product_ID) else 0)
    qty = x2.number_input("Quantity (units)", 1, 5000, 36, 1)
    p = opts[pick]
    disc = x3.slider("Requested discount (%)", 0, 50, 32, 1) / 100
    net_u = p.list_u * (1 - disc); gp_u = net_u - p.cogs; mgn = gp_u / net_u
    d_green = 1 - p.cogs / ((1 - green_m) * p.list_u); d_red = 1 - p.cogs / ((1 - red_m) * p.list_u)
    light = "GREEN" if mgn >= green_m else ("AMBER" if mgn >= red_m else "RED")
    kind = {"GREEN": "ok", "AMBER": "warn", "RED": "bad"}[light]
    msg = {"GREEN": "Sell. Margin meets the target.", "AMBER": "Needs Sales Manager approval: margin is below target.",
           "RED": "Blocked: below the cost floor. Finance exception only."}[light]
    
    k = st.columns(5)
    k[0].markdown(kpi("Signal", light, msg, light, kind), unsafe_allow_html=True)
    k[1].markdown(kpi("Net price / unit", f"{net_u:,.0f}", f"list {p.list_u:,.0f} - cost {p.cogs:,.0f} EGP"), unsafe_allow_html=True)
    k[2].markdown(kpi("Gross margin", f"{mgn:.1%}", f"{gp_u:,.0f} EGP per unit"), unsafe_allow_html=True)
    k[3].markdown(kpi("Deal gross profit", f"{gp_u*qty:,.0f}", f"on {net_u*qty:,.0f} EGP net sales"), unsafe_allow_html=True)
    k[4].markdown(kpi("Typical discount today", f"{p.today:.1%}", "this product, last 12 months"), unsafe_allow_html=True)
    st.write("")
    
    if d_green >= 0:
        counter = f"Counter-offer: up to **{min(d_green, disc if light == 'GREEN' else d_green):.0%}** keeps the green margin ({green_m:.0%}). Price floor (no loss): **{p.list_u*(1-max(d_red, 0)):,.0f} EGP/unit** ({max(d_red, 0):.0%} discount)."
    else:
        counter = f"Even at 0% discount this product earns less than the green margin. Price floor (no loss): **{p.list_u*(1-max(d_red, 0)):,.0f} EGP/unit**."
    st.markdown(counter)
    
    with st.container(border=True):
        dx = np.linspace(0, .5, 101); my = (p.list_u * (1 - dx) - p.cogs) / (p.list_u * (1 - dx))
        fig = go.Figure(); fig.add_scatter(x=dx, y=my, name="Margin", line=dict(color=PRIMARY))
        fig.add_hrect(y0=-1, y1=red_m, fillcolor="#FEE2E2", opacity=.5, line_width=0); fig.add_hrect(y0=red_m, y1=green_m, fillcolor="#FEF3C7", opacity=.5, line_width=0)
        fig.add_hrect(y0=green_m, y1=1, fillcolor="#DCFCE7", opacity=.4, line_width=0)
        fig.add_vrect(x0=.28, x1=.38, fillcolor="#93C5FD", opacity=.25, line_width=0, annotation_text="today's range", annotation_position="top left")
        fig.add_scatter(x=[disc], y=[mgn], mode="markers", marker=dict(size=12, color="#0B1B3A"), name="This quote")
        fig.update_xaxes(tickformat=".0%", title_text="Discount"); fig.update_yaxes(tickformat=".0%", range=[min(-.15, my.min() - .02), .5], title_text="Gross margin")
        plot(fig, 300, legend=True)
    hist = w12[w12.Product_ID == p.Product_ID]
    st.caption(f"In the last 12 months {len(hist):,} wholesale lines of this product sold; {(hist.Gross_Profit_EGP <= 0).mean():.0%} were at or below cost. "
               "Approval levels (Amber: Sales Manager, Red: Finance) are a proposed workflow, not an existing one. Cost = estimated COGS per unit.")

with t3:
    st.markdown("**Design the discount policy and test it on the last 12 months of real wholesale lines**")
    p1, p2, p3, p4 = st.columns(4)
    cap_s = p1.slider("Cap: small orders, up to 24 units (%)", 20, 38, 28, 1) / 100
    cap_m = p2.slider("Cap: medium, 25-36 units (%)", 20, 38, 30, 1) / 100
    cap_l = p3.slider("Cap: large, 37+ units (%)", 20, 38, 32, 1) / 100
    m_min = p4.slider("Minimum margin floor (%)", 0, 15, 5, 1) / 100
    vl = st.slider("Volume lost on lines whose price goes up (%)", 0, 30, 10, 1, help="No price-elasticity data exists in the dataset: this is the key assumption.") / 100

    def policy(d, caps, mmin, loss):
        tier = np.where(d.Quantity <= 24, caps[0], np.where(d.Quantity <= 36, caps[1], caps[2]))
        floor = np.clip(1 - d.Estimated_COGS_EGP / ((1 - mmin) * d.Gross_Sales_EGP), 0, 1)
        new = np.minimum(d.Discount_Pct, np.minimum(tier, floor)); cut = new < d.Discount_Pct - 1e-9
        keep = np.where(cut, 1 - loss, 1.0)
        return new, cut, d.Gross_Sales_EGP * (1 - new) * keep, (d.Gross_Sales_EGP * (1 - new) - d.Estimated_COGS_EGP) * keep

    new, cut, net_new, gp_new = policy(w12, (cap_s, cap_m, cap_l), m_min, vl)
    gp0, net0 = w12.Gross_Profit_EGP.sum(), w12.Net_Sales_EGP.sum(); d_gp = gp_new.sum() - gp0
    full = (w12.Gross_Sales_EGP * (1 - new) - w12.Estimated_COGS_EGP)[cut]; be = 1 - w12.Gross_Profit_EGP[cut].sum() / full.sum() if full.sum() > 0 else np.nan
    
    k = st.columns(5)
    k[0].markdown(kpi("Gross profit change", f"{d_gp/1e6:+,.2f}M", f"{d_gp/gp0:+.0%} on {gp0/1e6:,.1f}M EGP a year", "Per year", "ok" if d_gp > 0 else "bad"), unsafe_allow_html=True)
    k[1].markdown(kpi("Margin", f"{gp_new.sum()/net_new.sum():.1%}", f"from {gp0/net0:.1%}"), unsafe_allow_html=True)
    k[2].markdown(kpi("Lines affected", f"{cut.mean():.0%}", f"{int(cut.sum()):,} of {len(w12):,} lines"), unsafe_allow_html=True)
    k[3].markdown(kpi("Average discount", f"{(1 - (w12.Gross_Sales_EGP*(1-new)).sum()/w12.Gross_Sales_EGP.sum()):.1%}", f"from {1 - net0/w12.Gross_Sales_EGP.sum():.1%}"), unsafe_allow_html=True)
    k[4].markdown(kpi("Break-even volume loss", f"{be:.0%}" if be == be else "n/a", "policy pays unless more walks away", "Safety margin", "info"), unsafe_allow_html=True)
    st.write("")
    
    insight(f"The policy adds **{d_gp/1e6:+,.2f}M EGP** of gross profit a year even if **{vl:.0%}** of the volume on affected lines walks away, "
            f"and stays positive until the loss exceeds **{be:.0%}**. It also removes {int((w12.Gross_Profit_EGP <= 0).sum() - (((w12.Gross_Sales_EGP*(1-new) - w12.Estimated_COGS_EGP) <= 0).sum())):,} below-cost lines.")
    
    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown("**Sensitivity: single cap × volume lost (change in yearly gross profit, M EGP)**")
        caps = [.26, .28, .30, .32, .34, .36]; losses = [0, .05, .10, .15, .20]
        grid = pd.DataFrame({f"{int(l*100)}%": [(policy(w12, (c, c, c), m_min, l)[3].sum() - gp0) / 1e6 for c in caps] for l in losses}, index=[f"{int(c*100)}% cap" for c in caps])
        fig = px.imshow(grid.round(1), text_auto=".1f", color_continuous_scale="RdYlGn", color_continuous_midpoint=0, aspect="auto"); fig.update_layout(coloraxis_showscale=False)
        fig.update_xaxes(title_text="Volume lost on affected lines"); plot(fig, 300)
        st.caption("Green = more gross profit than today. The minimum-margin floor above is applied in every cell.")
    with b, st.container(border=True):
        st.markdown("**Margin by product: today vs policy (lowest 10 today)**")
        dd = w12.assign(gp_new=gp_new, net_new=net_new).groupby("Product_ID").agg(g0=("Gross_Profit_EGP", "sum"), n0=("Net_Sales_EGP", "sum"), g1=("gp_new", "sum"), n1=("net_new", "sum"))
        dd["Today"], dd["Policy"] = dd.g0 / dd.n0, dd.g1 / dd.n1; low = dd.nsmallest(10, "Today").reset_index().melt(id_vars="Product_ID", value_vars=["Today", "Policy"], var_name="Case", value_name="Margin")
        fig = px.bar(low, x="Product_ID", y="Margin", color="Case", barmode="group", color_discrete_map={"Today": "#CBD5E1", "Policy": PRIMARY}); fig.update_yaxes(tickformat=".0%"); plot(fig, 300, legend=True)
    st.caption("Data class: modeled transactions anchored to public products and prices. The data has no salesperson, quote or commission fields, so this page shows pricing outcomes, "
               "not individual behavior. The flat discount pattern may be partly an artifact of how the data was generated; the policy logic is what carries over to real data, and the volume-loss assumption should be tested on real quotes. "
               "Gross profit uses estimated COGS; changes are scenario estimates, not forecasts.")