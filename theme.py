"""Design system: colors, CSS, and small HTML helpers (KPI card, pill, header)."""
import streamlit as st

NAVY, BG, CARD, BORDER = "#0B1B3A", "#F4F6FA", "#FFFFFF", "#E5E9F0"
TEXT, MUTED, PRIMARY = "#0F172A", "#64748B", "#2563EB"
KIND = {  # (text, background)
    "ok": ("#15803D", "#DCFCE7"), "warn": ("#B45309", "#FEF3C7"),
    "bad": ("#B91C1C", "#FEE2E2"), "info": ("#1D4ED8", "#DBEAFE"), "muted": ("#475569", "#E2E8F0"),
}

def inject():
    st.markdown(f"""<style>
    .stApp {{ background:{BG}; }}
    .block-container {{ padding-top:1.4rem; max-width:1400px; }}
    [data-testid="stSidebar"] {{ background:{NAVY}; }}
    [data-testid="stSidebar"] * {{ color:#CBD5E1; }}
    [data-testid="stSidebarNav"] a {{ border-radius:8px; padding:4px 10px; }}
    [data-testid="stSidebarNav"] a[aria-current="page"] {{ background:{PRIMARY}; }}
    [data-testid="stSidebarNav"] a[aria-current="page"] * {{ color:#fff !important; font-weight:600; }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{ background:{CARD}; border-radius:12px; border:1px solid {BORDER}; }}
    .kpi {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px; padding:14px 16px; height:100%; min-height:112px; }}
    .kpi .l {{ color:{MUTED}; font-size:.78rem; }}
    .kpi .v {{ color:{TEXT}; font-size:1.55rem; font-weight:700; line-height:1.25; white-space:nowrap; }}
    .kpi .s {{ color:{MUTED}; font-size:.74rem; }}
    .pill {{ display:inline-block; padding:1px 9px; border-radius:999px; font-size:.72rem; font-weight:600; }}
    .pg-title {{ font-size:1.7rem; font-weight:800; color:{TEXT}; margin:0; }}
    .pg-sub {{ color:{MUTED}; margin:0 0 1rem 0; }}
    .tbl {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
    .tbl th {{ text-align:left; color:{MUTED}; font-weight:600; font-size:.72rem; padding:6px 8px; border-bottom:1px solid {BORDER}; }}
    .tbl td {{ padding:8px; border-bottom:1px solid {BORDER}; color:{TEXT}; }}
    [data-testid="stMarkdownContainer"] table.tbl th, [data-testid="stMarkdownContainer"] table.tbl td {{ border:none; border-bottom:1px solid {BORDER}; }}
    .insight {{ background:#EFF6FF; border-left:4px solid {PRIMARY}; padding:10px 14px; border-radius:8px; color:{TEXT}; margin-bottom:1rem; }}
    </style>""", unsafe_allow_html=True)

def header(title, subtitle="", kicker=""):
    k = f'<p style="color:{PRIMARY};font-weight:700;font-size:.8rem;margin:0">{kicker}</p>' if kicker else ""
    st.markdown(f'{k}<p class="pg-title">{title}</p><p class="pg-sub">{subtitle}</p>', unsafe_allow_html=True)

def pill(text, kind="muted"):
    c, b = KIND[kind]
    return f'<span class="pill" style="color:{c};background:{b}">{text}</span>'

def kpi(label, value, sub="", badge=None, kind="ok"):
    b = pill(badge, kind) if badge else ""
    return f'<div class="kpi"><div class="l">{label}</div><div class="v">{value} {b}</div><div class="s">{sub}</div></div>'

def insight(text):
    st.markdown(f'<div class="insight">💡 {text}</div>', unsafe_allow_html=True)

def stub(title, question, files, outputs, extra=""):
    """Placeholder page: states the business question, data, and deliverables."""
    header(title, question)
    with st.container(border=True):
        st.markdown("**Data used:** " + ", ".join(f"`{f}`" for f in files))
        st.markdown("**To build:**\n" + "\n".join(f"- {o}" for o in outputs))
        if extra: st.caption(extra)

PALETTE = ["#1D4ED8", "#3B82F6", "#93C5FD", "#CBD5E1"]

def plot(fig, h=280, legend=False):
    """Consistent chart styling."""
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", xaxis_title=None, yaxis_title=None,
                      font=dict(color=TEXT), showlegend=legend)
    fig.update_yaxes(gridcolor=BORDER)
    st.plotly_chart(fig, width="stretch")
