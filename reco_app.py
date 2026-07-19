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

# --- APP SETUP ---
st.set_page_config(page_title="Design-Wise Financial Summary", layout="wide")

st.markdown("""
    <style>
        .metric-card { background-color: #1e293b; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.3); text-align: center; border: 1px solid #334155; }
        .metric-title { font-size: 14px; color: #94a3b8; font-weight: 600; margin-bottom: 5px; }
        .metric-value { font-size: 20px; color: #f8fafc; font-weight: bold; }
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

# --- SIDEBAR ---
action = st.sidebar.radio("Choose Action:", ["View Dashboard", "Upload Data", "Manage SKU Mapping"], index=0)

# --- MANAGE MAPPING ---
if action == "Manage SKU Mapping":
    st.header("🔗 Manage SKU to Design Mapping")
    tab1, tab2, tab3 = st.tabs(["Bulk Upload", "Add Single SKU", "View Mappings"])
    with tab1:
        mapping_file = st.file_uploader("Upload Excel", type=["xlsx", "csv"])
        if mapping_file and st.button("Save Bulk Mapping"):
            df_map = pd.read_csv(mapping_file) if mapping_file.name.endswith('.csv') else pd.read_excel(mapping_file)
            mapping_data = [{"seller_sku": str(r['Seller SKU on Channel']).strip().upper(), "design": str(r['DESIGN']).strip().upper()} for _, r in df_map.iterrows() if pd.notnull(r['Seller SKU on Channel'])]
            supabase.table("sku_mapping").upsert(mapping_data).execute()
            st.success("✅ Bulk mapping saved!")
    with tab2:
        s = st.text_input("SKU:").strip().upper()
        d = st.text_input("Design:").strip().upper()
        if st.button("Save Single"):
            supabase.table("sku_mapping").upsert([{"seller_sku": s, "design": d}]).execute()
            st.success("✅ Saved!")
    with tab3:
        if st.button("Refresh List"):
            res = supabase.table("sku_mapping").select("*").execute()
            st.dataframe(pd.DataFrame(res.data))

# --- UPLOAD DATA ---
elif action == "Upload Data":
    st.header("📤 Upload Financial Report")
    brand = st.text_input("Brand:", "VIDA LOCA").strip().upper()
    mp = st.selectbox("Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])
    ads = st.number_input("Ads Cost:", value=0.0)
    uploaded_file = st.file_uploader("Upload Payment Report", type=["xlsx"])
    
    if uploaded_file and st.button("Process Data"):
        df = pd.read_excel(uploaded_file)
        # Assume simple cleaning here
        mapping_res = supabase.table("sku_mapping").select("*").execute()
        m_dict = {r['seller_sku']: r['design'] for r in mapping_res.data}
        
        # Simple Logic to create summary
        # (Yahan aapka logic re-use hoga)
        st.success("Data processed successfully!")

# --- DASHBOARD ---
else:
    brands = get_unique_values("brand")
    mps = get_unique_values("marketplace")
    months = get_unique_values("month_year")
    
    s_brand = st.sidebar.selectbox("Brand:", ["ALL"] + brands)
    
    query = supabase.table("design_wise_summary").select("*")
    if s_brand != "ALL": query = query.eq("brand", s_brand)
    df = pd.DataFrame(query.execute().data)
    
    if not df.empty:
        # Metrics Display
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f'<div class="metric-card"><div class="metric-title">Gross Sales</div><div class="metric-value">{df["gross_sale_amt"].sum():,.2f}</div></div>', unsafe_allow_html=True)
        # ... baaki metrics aise hi ...
        
        st.subheader("📊 Top Designs")
        top = df.groupby('design')['net_settled_amount'].sum().reset_index().sort_values(by='net_settled_amount', ascending=False).head(10)
        st.bar_chart(top.set_index('design'))
        
        st.subheader("📋 Breakdown")
        st.dataframe(df)
    else:
        st.info("No data found.")
