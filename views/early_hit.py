import streamlit as st
import pandas as pd
import joblib
from pathlib import Path
import datetime
import html

try:
    from notifier import send_alert
except ImportError:
    send_alert = None

st.set_page_config(page_title="Early Hit Detector", layout="wide")

potential_paths = [
    Path("data/early_hit_model.pkl"),
    Path(__file__).resolve().parents[1] / "data" / "early_hit_model.pkl",
    Path(__file__).resolve().parent / "data" / "early_hit_model.pkl",
]

MODEL_PATH = None
for p in potential_paths:
    if p.exists():
        MODEL_PATH = p
        break

if MODEL_PATH is None:
    MODEL_PATH = Path("data/early_hit_model.pkl")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-left: 3rem; padding-right: 3rem; max-width: 100%; }

    .result-banner {
        border-radius: 14px;
        padding: 22px 26px;
        margin: 8px 0 18px 0;
        border-left: 8px solid var(--accent);
        background: var(--bg);
    }
    .result-banner .eyebrow {
        font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase;
        opacity: 0.75; margin-bottom: 4px;
    }
    .result-banner .status {
        font-size: 2rem; font-weight: 700; color: var(--accent); line-height: 1.15;
    }
    .result-banner .meta { font-size: 0.92rem; opacity: 0.85; margin-top: 6px; }

    .badge {
        display: inline-block; padding: 3px 12px; border-radius: 999px;
        font-size: 0.78rem; font-weight: 600; color: #fff; background: var(--accent);
        margin-left: 10px; vertical-align: middle;
    }

    .prob-wrap { margin: 6px 0 22px 0; }
    .prob-label {
        display: flex; justify-content: space-between;
        font-size: 0.85rem; opacity: 0.85; margin-bottom: 6px;
    }
    .prob-track {
        position: relative; height: 14px; border-radius: 999px;
        background: rgba(128,128,128,0.25); overflow: visible;
    }
    .prob-fill { height: 100%; border-radius: 999px; background: var(--accent); }
    .prob-mark {
        position: absolute; top: -5px; left: 50%; width: 2px; height: 24px;
        background: rgba(128,128,128,0.9);
    }
    .prob-scale {
        display: flex; justify-content: space-between;
        font-size: 0.72rem; opacity: 0.6; margin-top: 4px;
    }

    .kpi-card {
        border: 1px solid rgba(128,128,128,0.28);
        border-radius: 12px; padding: 14px 16px; height: 100%;
    }
    .kpi-card .k-label {
        font-size: 0.74rem; text-transform: uppercase;
        letter-spacing: 0.06em; opacity: 0.7;
    }
    .kpi-card .k-value { font-size: 1.45rem; font-weight: 700; margin-top: 2px; }
    .kpi-card .k-sub { font-size: 0.8rem; opacity: 0.7; margin-top: 2px; }

    .action-box {
        border-radius: 12px; padding: 18px 22px; margin-top: 18px;
        background: var(--bg); border: 1px solid var(--accent);
    }
    .action-box h4 { margin: 0 0 8px 0; color: var(--accent); font-size: 1.05rem; }
    .action-box ul { margin: 6px 0 0 0; padding-left: 20px; }
    .action-box li { margin-bottom: 4px; }

    .section-title {
        font-size: 1.1rem; font-weight: 700; margin: 26px 0 10px 0;
        padding-bottom: 6px; border-bottom: 1px solid rgba(128,128,128,0.3);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def kpi(label: str, value: str, sub: str = "") -> str:
    return (
        f'<div class="kpi-card"><div class="k-label">{label}</div>'
        f'<div class="k-value">{value}</div><div class="k-sub">{sub}</div></div>'
    )

st.title("Early Hit Detector")
st.markdown(
    "Predict product success (**Top Performer** or **At-Risk**) after just 7 days "
    "of its launch in the market.\n\n"
    "*(Note: A 'Top Performer' is defined by the AI as a product projected to be in the top 30% of sales volume over its first 60 days).*"
)

@st.cache_resource
def load_model():
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None

model = load_model()

if model is None:
    st.error(f"Model not found! Python is looking in this path: {MODEL_PATH.absolute()}")
else:
    with st.container(border=True):
        st.markdown("#### Product Details & 7-Day Performance")

        c1, c2 = st.columns(2)
        with c1:
            prod_name = st.text_input(
                "Product Code / Name", placeholder="e.g., P-1092 (Winter Jacket)"
            )
        with c2:
            default_date = datetime.date.today() - datetime.timedelta(days=7)
            launch_date = st.date_input("Launch Date", value=default_date)

        st.write("")

        col1, col2, col3 = st.columns(3)
        with col1:
            qty = st.number_input("Quantity Sold (Units)", min_value=0, value=150)
        with col2:
            sales = st.number_input("Total Sales (EGP)", min_value=0, value=45000, step=1000)
        with col3:
            customers = st.number_input("Unique Customers", min_value=0, value=25)

        run_btn = st.button("Run AI", type="primary", use_container_width=True)

    if run_btn:
        if not prod_name.strip():
            st.warning("Please enter a Product Code or Name before running the forecast.")
        else:
            with st.spinner(f"Analyzing pattern for {prod_name}..."):
                input_data = pd.DataFrame(
                    [[qty, sales, customers]],
                    columns=["qty_7d", "sales_7d", "customers_7d"],
                )
                prediction = model.predict(input_data)[0]
                probability = model.predict_proba(input_data)[0][1] * 100

            is_top = prediction == 1
            safe_name = html.escape(prod_name.strip())

            if is_top:
                accent = "#16a34a"
                bg = "rgba(22,163,74,0.10)"
                status = "Top Performer"
                badge = "High Potential"
                recommendation = "Scale Up"
                rec_sub = "Immediate action"
                confidence = probability
                risk = "Low"
                actions = [
                    "Increase production quotas immediately to avoid stockouts.",
                    "Secure raw materials and supplier capacity for the next cycle.",
                    "Prioritize this product in marketing and top shelf placement.",
                ]
                action_title = "Recommended Action Plan"
                summary = (
                    "Based on the first 7 days of sales data, this product shows strong "
                    "market traction and is projected to be a Top Performer."
                )
            else:
                accent = "#dc2626"
                bg = "rgba(220,38,38,0.08)"
                status = "At-Risk"
                badge = "Slow Mover"
                recommendation = "Halt Scaling"
                rec_sub = "Monitor inventory"
                confidence = 100 - probability
                risk = "High"
                actions = [
                    "Halt overproduction and avoid re-ordering raw materials.",
                    "Closely monitor current inventory to minimize tied-up capital.",
                    "Consider promotions or bundling to lift early demand.",
                ]
                action_title = "Recommended Action Plan"
                summary = (
                    "This product is currently underperforming compared to historical "
                    "success benchmarks."
                )

            if send_alert:
                icon = "[+]" if status == "Top Performer" else "[-]"
                alert_msg = (
                    f"{icon} *El-Sharnouby Executive Brief*\n\n"
                    f"*Product:* {safe_name}\n"
                    f"*AI Forecast:* {status}\n"
                    f"*Success Probability:* {probability:.1f}%\n"
                    f"*7-Day Revenue:* {sales:,.0f} EGP\n\n"
                    f"*Action Required:*\n- {actions[0]}"
                )
                send_alert(alert_msg)
                st.toast("Telegram Alert Sent to Executive!")

            st.markdown('<div class="section-title">AI Results</div>', unsafe_allow_html=True)

            st.markdown(
                f"""
                <div class="result-banner" style="--accent:{accent}; --bg:{bg};">
                    <div class="eyebrow">Forecast for {safe_name}</div>
                    <div class="status">{status}<span class="badge">{badge}</span></div>
                    <div class="meta">{summary}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class="prob-wrap" style="--accent:{accent};">
                    <div class="prob-label">
                        <span>Success probability</span>
                        <strong>{probability:.1f}%</strong>
                    </div>
                    <div class="prob-track">
                        <div class="prob-fill" style="width:{probability:.1f}%;"></div>
                        <div class="prob-mark"></div>
                    </div>
                    <div class="prob-scale"><span>0%</span><span>50% threshold</span><span>100%</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            k1, k2, k3 = st.columns(3)
            k1.markdown(kpi("Model Confidence", f"{confidence:.1f}%", "In predicted class"), unsafe_allow_html=True)
            k2.markdown(kpi("Risk Level", risk, "Based on 7-day signal"), unsafe_allow_html=True)
            k3.markdown(kpi("Recommendation", recommendation, rec_sub), unsafe_allow_html=True)

            items = "".join(f"<li>{a}</li>" for a in actions)
            st.markdown(
                f"""
                <div class="action-box" style="--accent:{accent}; --bg:{bg};">
                    <h4>{action_title}</h4>
                    <ul>{items}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div class="section-title">Performance Breakdown</div>', unsafe_allow_html=True)

            avg_price = sales / qty if qty else 0
            sales_per_customer = sales / customers if customers else 0
            units_per_customer = qty / customers if customers else 0
            daily_sales = sales / 7

            d1, d2, d3, d4 = st.columns(4)
            d1.markdown(kpi("Avg. Price / Unit", f"{avg_price:,.0f}", "EGP"), unsafe_allow_html=True)
            d2.markdown(kpi("Sales / Customer", f"{sales_per_customer:,.0f}", "EGP"), unsafe_allow_html=True)
            d3.markdown(kpi("Units / Customer", f"{units_per_customer:.1f}", "Units"), unsafe_allow_html=True)
            d4.markdown(kpi("Avg. Daily Sales", f"{daily_sales:,.0f}", "EGP / day"), unsafe_allow_html=True)

            st.write("")
            with st.expander("View input summary"):
                summary_df = pd.DataFrame(
                    {
                        "Field": [
                            "Product",
                            "Launch Date",
                            "Quantity Sold (Units)",
                            "Total Sales (EGP)",
                            "Unique Customers",
                        ],
                        "Value": [
                            prod_name.strip(),
                            str(launch_date),
                            f"{qty:,}",
                            f"{sales:,}",
                            f"{customers:,}",
                        ],
                    }
                )
                st.dataframe(summary_df, hide_index=True, use_container_width=True)