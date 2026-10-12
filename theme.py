import streamlit as st

PRIMARY = "#1D4ED8"
PALETTE = ["#1D4ED8", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"]

def inject():
    
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def header(title, subtitle="", kicker=""):
    st.markdown(f"## {title} <span style='color: #1D4ED8; font-size: 14px;'>{kicker}</span>", unsafe_allow_html=True)
    st.markdown(f"**{subtitle}**")
    st.markdown("---")

def kpi(label, value, sub="", badge=None, kind="ok"):
    
    colors = {"ok": "#10B981", "warn": "#F59E0B", "bad": "#EF4444", "info": "#3B82F6"}
    c = colors.get(kind, "#333")
    
    return f'''
    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <div style="color: #64748b; font-size: 13px; font-weight: bold; text-transform: uppercase;">{label}</div>
        <div style="color: #0f172a; font-size: 24px; font-weight: bold; margin: 5px 0;">{value}</div>
        <div style="color: {c}; font-size: 12px; font-weight: bold;">{badge if badge else ""} <span style="color: #94a3b8; font-weight: normal;">{sub}</span></div>
    </div>
    '''

def pill(text, kind="ok"):
    return text

def insight(text):
    st.info(text)

def plot(fig, h=280, legend=False):
    
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=20, b=0), showlegend=legend)
    st.plotly_chart(fig, use_container_width=True)