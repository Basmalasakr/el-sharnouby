import streamlit as st
from theme import inject

st.set_page_config(page_title="El-Sharnouby Group | Decision Hub", page_icon="", layout="wide")
inject()
with st.sidebar:
    st.markdown("### \n<span style='font-size:.7rem'>  </span>", unsafe_allow_html=True)

P = lambda f, t, i, **k: st.Page(f"views/{f}.py", title=t, icon=i, **k)
nav = st.navigation({
    "Overview": [P("control_tower", "Executive Command Center", "", default=True)],
    "Operations": [P("inventory", "Smart Inventory & Replenishment", ""), P("factory", "Factory & Printing", ""), P("quality", "Quality & Returns", ""),
                   P("procurement", "Procurement & Risk", "")],
    "Commercial": [P("customers", "Customer 360", ""), P("marketing", "Marketing & Growth", ""),
                   P("branches", "Channel & Expansion", "")],
    "Final Mission": [P("final_mission", "Wholesale Deal Desk", "")],
    "Evidence": [P("evidence", "Data & Evidence", "")]
})
nav.run()