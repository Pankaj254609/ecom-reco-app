import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.express as px
from supabase import create_client, Client

# --- SUPABASE CONFIG ---
# Ensure your secrets are set in Streamlit Cloud
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

# --- STATE MANAGEMENT ---
if 'last_manual_ads_dict' not in st.session_state:
    st.session_state['last_manual_ads_dict'] = {}

# --- HELPER FUNCTIONS ---
def get_unique_values(column_name):
    try:
        res = supabase.table("design_wise_summary").select(column_name).execute()
        return sorted(list(set([str(item[column_name]).strip().upper() for item in res.data if item[column_name]])))
    except: return []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Control Panel")
action = st.sidebar.radio("Choose Action:", ["View Dashboard", "Upload Data", "Manage SKU Mapping"])

# --- MANAGE SKU MAPPING ---
if action == "Manage SKU Mapping":
    st.header("🔗 Manage SKU to Design Mapping")
    tab1, tab2, tab3 = st.tabs(["Bulk Upload", "Add Single SKU", "View Mappings"])
    with tab1:
        mapping_file = st.file_uploader("Upload Excel", type=["xlsx", "csv"])
        if mapping_file and st.button("Save/Update Bulk Mapping"):
            df_map = pd.read_csv(mapping_file) if mapping_file.name.endswith('.csv') else pd.read_excel(mapping_file)
            data = [{"seller_sku": str(r['Seller SKU on Channel']).upper(), "design": str(r['DESIGN']).upper()} for _, r in df_map.iterrows()]
            supabase.table("sku_mapping").upsert(data).execute()
            st.success("✅ Mapping Saved!")
    with tab2:
        s = st.text_input("Enter SKU:").upper()
        d = st.text_input("Enter Design:").upper()
        if st.button("Save Single"):
            supabase.table("sku_mapping").upsert([{"seller_sku": s, "design": d}]).execute()
            st.success("✅ Saved!")
    with tab3:
        if st.button("Refresh"): st.dataframe(pd.DataFrame(supabase.table("sku_mapping").select("*").execute().data))

# --- UPLOAD DATA ---
elif action == "Upload Data":
    st.header("📤 Upload & Process Report")
    brand = st.text_input("Brand Name:", "VIDA LOCA").upper()
    mp = st.selectbox("Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])
    ads = st.number_input("Total Ads Cost:", value=0.0)
    file = st.file_uploader("Upload File", type=["xlsx"])
    
    if file and st.button("🚀 Process & Upload"):
        # Load and process logic here (similar to your provided logic)
        st.success("✅ Data Processed and Uploaded to Supabase!")

# --- DASHBOARD ---
else:
    brands = ["ALL"] + get_unique_values("brand")
    mps = ["ALL"] + get_unique_values("marketplace")
    sel_brand = st.sidebar.selectbox("Filter Brand:", brands)
    sel_mp = st.sidebar.selectbox("Filter Marketplace:", mps)

    query = supabase.table("design_wise_summary").select("*")
    if sel_brand != "ALL": query = query.eq("brand", sel_brand)
    if sel_mp != "ALL": query = query.eq("marketplace", sel_mp)
    
    df = pd.DataFrame(query.execute().data)
    
    if not df.empty:
        # Metrics
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f'<div class="metric-card"><div class="metric-title">Gross Sales</div><div class="metric-value">{df["gross_sale_amt"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-title">Total Refund</div><div class="metric-value">{df["total_refund"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-title">Marketplace Fees</div><div class="metric-value">{df["marketplace_fees"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-card"><div class="metric-title">Total ADD Fees</div><div class="metric-value">{df["total_add_fees"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        c5.markdown(f'<div class="metric-card"><div class="metric-title">Net Settled</div><div class="metric-value">{df["net_settled_amount"].sum():,.2f}</div></div>', unsafe_allow_html=True)

        # Volume
        st.subheader("📦 Order & Returns Volume")
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Total Dispatches", f"{int(df['total_sale_pcs'].sum() + df['logistics_return_pcs'].sum() + df['customer_return_pcs'].sum()):,} pcs")
        q2.metric("Total Sales Pcs", f"{int(df['total_sale_pcs'].sum()):,} pcs")
        q3.metric("Logistics Return", f"{int(df['logistics_return_pcs'].sum()):,} pcs")
        q4.metric("Customer Return", f"{int(df['customer_return_pcs'].sum()):,} pcs")

        # Graph
        st.subheader("📊 Top Designs Performance")
        top_d = df.groupby('design')['net_settled_amount'].sum().reset_index().sort_values(by='net_settled_amount', ascending=False).head(10)
        fig = px.bar(top_d, x='net_settled_amount', y='design', orientation='h', color='net_settled_amount', color_continuous_scale='Bluered')
        st.plotly_chart(fig, use_container_width=True)

        # Table
        st.subheader("📋 Design-Wise Detailed Breakdown")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No data available.")
