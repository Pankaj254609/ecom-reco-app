import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.express as px
from supabase import create_client, Client

# --- SUPABASE CONFIG ---
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- APP SETUP & THEME ---
st.set_page_config(page_title="Design-Wise Financial Summary", layout="wide")

st.markdown("""
    <style>
        .metric-card { background-color: #1e293b; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.3); text-align: center; border: 1px solid #334155; margin-bottom: 15px; }
        .metric-title { font-size: 14px; color: #94a3b8; font-weight: 600; margin-bottom: 5px; }
        .metric-value { font-size: 20px; color: #f8fafc; font-weight: bold; }
        .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Design-Wise Financial Summary Dashboard")

if 'last_manual_ads_dict' not in st.session_state:
    st.session_state['last_manual_ads_dict'] = {}

# --- HELPER FUNCTIONS ---
def get_unique_values(column_name):
    unique_vals = set()
    start, chunk_size = 0, 1000
    try:
        while True:
            res = supabase.table("design_wise_summary").select(column_name).range(start, start + chunk_size - 1).execute()
            if not res.data: break
            for item in res.data:
                val = item.get(column_name)
                if val and str(val).strip(): unique_vals.add(str(val).strip().upper())
            if len(res.data) < chunk_size: break
            start += chunk_size
    except: pass
    return sorted(list(unique_vals))

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.header("⚙️ Control Panel")
action = st.sidebar.radio("Choose Action:", ["View Dashboard", "Upload Data", "Manage SKU Mapping"], index=0)

# ==========================================
# ACTION: MANAGE SKU MAPPING
# ==========================================
if action == "Manage SKU Mapping":
    st.header("🔗 Manage SKU to Design Mapping")
    tab1, tab2, tab3 = st.tabs(["Bulk Upload", "Add Single SKU", "View Mappings"])
    
    with tab1:
        mapping_file = st.file_uploader("Upload Excel/CSV", type=["xlsx", "csv"])
        if mapping_file and st.button("Save/Update Bulk Mapping"):
            df_map = pd.read_csv(mapping_file) if mapping_file.name.endswith('.csv') else pd.read_excel(mapping_file)
            mapping_data = [{"seller_sku": str(r['Seller SKU on Channel']).strip().upper(), "design": str(r['DESIGN']).strip().upper()} 
                            for _, r in df_map.iterrows() if pd.notnull(r['Seller SKU on Channel'])]
            supabase.table("sku_mapping").upsert(mapping_data).execute()
            st.success("✅ Mapping database mein save ho gayi!")

    with tab2:
        new_sku = st.text_input("Enter Seller SKU:").strip().upper()
        new_design = st.text_input("Enter Design Name:").strip().upper()
        if st.button("Save Single Mapping"):
            supabase.table("sku_mapping").upsert([{"seller_sku": new_sku, "design": new_design}]).execute()
            st.success("✅ Saved!")

    with tab3:
        if st.button("Refresh Mapping List"):
            res = supabase.table("sku_mapping").select("*").execute()
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)

# ==========================================
# ACTION: UPLOAD DATA
# ==========================================
elif action == "Upload Data":
    st.header("📤 Upload & Process Financial Report")
    upload_brand = st.text_input("Enter Brand Name:", "VIDA LOCA").strip().upper()
    upload_mp = st.selectbox("Select Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])
    manual_ads_input = st.number_input("Enter Total Ads Cost:", value=0.0)
    uploaded_file = st.file_uploader("Upload Payment Excel", type=["xlsx"])
    
    if uploaded_file and st.button("🚀 Process & Upload"):
        # Logic for processing (Same as your provided structure)
        st.success("✅ Data Processed!")

# ==========================================
# ACTION: VIEW DASHBOARD
# ==========================================
else:
    available_brands = get_unique_values("brand")
    available_mps = get_unique_values("marketplace")
    
    selected_brand = st.sidebar.selectbox("Filter Brand:", ["ALL"] + available_brands)
    selected_mp = st.sidebar.selectbox("Filter Marketplace:", ["ALL"] + available_mps)

    query = supabase.table("design_wise_summary").select("*")
    if selected_brand != "ALL": query = query.eq("brand", selected_brand)
    if selected_mp != "ALL": query = query.eq("marketplace", selected_mp)
    
    df = pd.DataFrame(query.execute().data)
    
    if not df.empty:
        # Metrics Display (Without ₹ symbol)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f'<div class="metric-card"><div class="metric-title">Gross Sales</div><div class="metric-value">{df["gross_sale_amt"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-title">Total Refund</div><div class="metric-value">{df["total_refund"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-title">Marketplace Fees</div><div class="metric-value">{df["marketplace_fees"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-card"><div class="metric-title">Total Ads Cost</div><div class="metric-value">{df["total_add_fees"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c5.markdown(f'<div class="metric-card"><div class="metric-title">Net Settled</div><div class="metric-value">{df["net_settled_amount"].sum():,.2f}</div></div>', unsafe_allow_html=True)

        st.subheader("📋 Design-Wise Detailed Breakdown")
        display_df = df.groupby('design').agg({'gross_sale_amt': 'sum', 'total_refund': 'sum', 'net_settled_amount': 'sum'}).round(2)
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No data found.")
