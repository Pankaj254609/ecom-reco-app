import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client

# --- Page Config ---
st.set_page_config(page_title="Multi-Brand E-commerce Dashboard", layout="wide")
st.title("📊 डिज़ाइन-वाइज़, मंथ-वाइज़ और ब्रांड-वाइज़ ओवरऑल समरी डैशबोर्ड")

# --- Direct Supabase Database Connection (No Sidebar Input Needed) ---
@st.cache_resource
def init_supabase() -> Client:
    # Direct Production Keys (No fallback input boxes anymore)
    url = "https://tpbbngotolgthytgjarp.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwYmJuZ290b2xndGh5dGdqYXJwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTe4MzczNjc1MywiZXhwIjoyMDk5MzEyNzUzfQ.OuKXzzsjce5J9Ak6_Fu6GQTeK7mz37BCrX21HWG1DF8"
    return create_client(url, key)

# Safe Initialize Client
try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Supabase connection initialize karne mein dikkat aayi: {e}")
    st.stop()


# --- Load Cloud Data ---
@st.cache_data(ttl=60)
def load_cloud_data():
    try:
        res = supabase.table("design_wise_summary").select("*").limit(15000).execute()
        df = pd.DataFrame(res.data)
        return df
    except Exception as e:
        return pd.DataFrame()

df_design = load_cloud_data()


# --- Helper to Clean Numbers ---
def get_num_val(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).replace('₹', '').replace(',', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


# --- Functions to Process Individual Marketplace Sheets ---
def process_flipkart(df, brand_name):
    df['Month'] = df['Payment Date'].fillna('Unknown')
    df['Marketplace'] = 'FLIPKART'
    df['Brand'] = brand_name
    
    df['DEL_QTY'] = np.where(df['Return Type'].str.upper() == 'DEL', df['Quantity'], 0)
    df['DTO_QTY'] = np.where(df['Return Type'].str.upper() == 'DTO', df['Quantity'], 0)
    df['RTO_QTY'] = np.where(df['Return Type'].str.upper() == 'RTO', df['Quantity'], 0)
    df['ACTUAL_QTY'] = np.where(df['Return Type'].str.upper() == 'DEL', df['Quantity'], 0)
    
    df['Sale Amount'] = df['Sale Amount'].apply(get_num_val)
    df['Return Amount'] = df['Refund (Rs.)'].apply(get_num_val)
    df['Marketplace Fee'] = df['Marketplace Fee'].apply(get_num_val) + df['Taxes (Rs.)'].apply(get_num_val)
    df['ADD_FEES'] = df['Settlement Value ADD'].apply(get_num_val)
    df['Settlement Amount'] = df['Bank Settlement'].apply(get_num_val)
    
    return df[['Month', 'Marketplace', 'Brand', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']]

def process_meesho(df, brand_name):
    df['Month'] = df['Payment Date'].fillna('Unknown')
    df['Marketplace'] = 'MEESHO'
    df['Brand'] = brand_name
    
    status_col = 'Live Order Status' if 'Live Order Status' in df.columns else 'Status'
    df['DEL_QTY'] = np.where(df[status_col].str.upper() == 'DEL', df['QTY'], 0)
    df['DTO_QTY'] = np.where(df[status_col].str.upper() == 'DTO', df['QTY'], 0)
    df['RTO_QTY'] = np.where(df[status_col].str.upper() == 'RTO', df['QTY'], 0)
    df['ACTUAL_QTY'] = np.where(df[status_col].str.upper() == 'DEL', df['QTY'], 0)
    
    df['Sale Amount'] = df['Total Sale Amount (Incl. Shipping & GST)'].apply(get_num_val)
    df['Return Amount'] = df['Total Sale Return Amount'].apply(get_num_val)
    df['Marketplace Fee'] = df['total comission'].apply(get_num_val)
    df['ADD_FEES'] = df['ADD'].apply(get_num_val) if 'ADD' in df.columns else 0
    df['Settlement Amount'] = df['Final Settlement Amount'].apply(get_num_val)
    
    return df[['Month', 'Marketplace', 'Brand', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']]

def process_amazon(df, brand_name):
    df['Marketplace'] = 'AMAZON'
    df['Brand'] = brand_name
    df['DESIGN'] = df['DESIGN'].fillna('UNKNOWN')
    
    df['DEL_QTY'] = np.where(df['TYPE'].str.upper() == 'DEL', df['quantity'], 0)
    df['DTO_QTY'] = np.where(df['TYPE'].str.upper() == 'DTO', df['quantity'], 0)
    df['RTO_QTY'] = np.where(df['TYPE'].str.upper() == 'RTO', df['quantity'], 0)
    df['ACTUAL_QTY'] = np.where(df['TYPE'].str.upper() == 'DEL', df['quantity'], 0)
    
    df['Sale Amount'] = np.where(df['TYPE'].str.upper() == 'DEL', df['product sales'].apply(get_num_val), 0)
    df['Return Amount'] = np.where(df['TYPE'].str.upper().isin(['RTO','DTO']), df['product sales'].apply(get_num_val), 0)
    df['Marketplace Fee'] = np.where(df['TYPE'].str.upper() == 'FEES', df['TOTAL'].apply(get_num_val), 0)
    df['ADD_FEES'] = np.where(df['TYPE'].str.upper() == 'ADD', df['TOTAL'].apply(get_num_val), 0)
    df['Settlement Amount'] = df['TOTAL'].apply(get_num_val)
    
    return df[['MONTH', 'Marketplace', 'Brand', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']].rename(columns={'MONTH': 'Month'})

def process_myntra(df, brand_name):
    df['Marketplace'] = 'MYNTRA'
    df['Brand'] = brand_name
    
    df['DEL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    df['DTO_QTY'] = np.where(df['return_type'].str.upper() == 'DTO', df['QTY'], 0)
    df['RTO_QTY'] = np.where(df['return_type'].str.upper() == 'RTO', df['QTY'], 0)
    df['ACTUAL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    
    df['Sale Amount'] = df['seller_product_amount'].apply(get_num_val)
    df['Return Amount'] = 0 
    df['Marketplace Fee'] = df['total_commission_plus_tcs_tds_deduction'].apply(get_num_val)
    df['ADD_FEES'] = 0
    df['Settlement Amount'] = df['total_actual_settlement'].apply(get_num_val)
    
    return df[['MONTH', 'Marketplace', 'Brand', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']].rename(columns={'MONTH': 'Month'})

def process_snapdeal(df, brand_name):
    df['Marketplace'] = 'SNAPDEAL'
    df['Brand'] = brand_name
    
    df['DEL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    df['DTO_QTY'] = np.where(df['return_type'].str.upper() == 'DTO', df['QTY'], 0)
    df['RTO_QTY'] = np.where(df['return_type'].str.upper() == 'RTO', df['QTY'], 0)
    df['ACTUAL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    
    df['Sale Amount'] = df['seller_product_amount'].apply(get_num_val)
    df['Return Amount'] = 0
    df['Marketplace Fee'] = df['total_Commission_plus_tcs_tds_deduction'].apply(get_num_val)
    df['ADD_FEES'] = df['ADD'].apply(get_num_val)
    df['Settlement Amount'] = df['Settled'].apply(get_num_val)
    
    return df[['MONTH', 'Marketplace', 'Brand', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']].rename(columns={'MONTH': 'Month'})


# --- Sidebar: Multi-Brand & File Upload Panel ---
st.sidebar.markdown("## 📤 Sheet Upload & Management")

# Existing brands load list to avoid typos
existing_brands = ['TERRADESI']
if not df_design.empty:
    # Handle lowercase match for Supabase schema safely
    b_col = 'brand' if 'brand' in df_design.columns else 'Brand'
    if b_col in df_design.columns:
        unique_b = list(df_design[b_col].dropna().unique())
        if unique_b: existing_brands = unique_b

# 1. Select Brand Name or add new one
upload_brand_mode = st.sidebar.radio("Brand Select Type:", ["Existing Brand", "Add New Brand"])
if upload_brand_mode == "Existing Brand":
    upload_brand = st.sidebar.selectbox("Brand Name:", existing_brands)
else:
    upload_brand = st.sidebar.text_input("New Brand Name likhein:", "").strip().upper()

# 2. Select Marketplace
mp_type = st.sidebar.selectbox("Marketplace Select Karein:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA", "SNAPDEAL"])
uploaded_file = st.sidebar.file_uploader(f"{mp_type} Ki Sheet Upload Karein", type=["xlsx", "csv"])

if uploaded_file is not None and upload_brand != "":
    if st.sidebar.button("🚀 Process & Generate Summary"):
        with st.spinner("Sheet analyze aur calculate ho rahi hai..."):
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file)
                else:
                    df_raw = pd.read_excel(uploaded_file)
                
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                
                if mp_type == "FLIPKART": df_processed = process_flipkart(df_raw, upload_brand)
                elif mp_type == "MEESHO": df_processed = process_meesho(df_raw, upload_brand)
                elif mp_type == "AMAZON": df_processed = process_amazon(df_raw, upload_brand)
                elif mp_type == "MYNTRA": df_processed = process_myntra(df_raw, upload_brand)
                elif mp_type == "SNAPDEAL": df_processed = process_snapdeal(df_raw, upload_brand)
                
                df_processed = df_processed.dropna(subset=['DESIGN', 'Month'])
                df_processed = df_processed[df_processed['DESIGN'].astype(str).str.strip() != '']
                
                # --- AUTO-AGGREGATION with Brand column ---
                summary_df = df_processed.groupby(['Month', 'Marketplace', 'Brand', 'DESIGN']).agg({
                    'Sale Amount': 'sum',
                    'Return Amount': 'sum',
                    'Marketplace Fee': 'sum',
                    'DEL_QTY': 'sum',
                    'DTO_QTY': 'sum',
                    'RTO_QTY': 'sum',
                    'ACTUAL_QTY': 'sum',
                    'ADD_FEES': 'sum',
                    'Settlement Amount': 'sum'
                }).reset_index()
                
                db_records = summary_df.to_dict(orient='records')
                
                # Dynamic lowercase keys for matching database column architecture
                db_records_clean = []
                for record in db_records:
                    db_records_clean.append({k.lower().replace(' ', '_'): v for k, v in record.items()})

                # Delete existing data for that specific brand and channel to update freshly
                supabase.table("design_wise_summary").delete().eq("marketplace", mp_type).eq("brand", upload_brand).execute()
                
                chunk_size = 200
                for i in range(0, len(db_records_clean), chunk_size):
                    supabase.table("design_wise_summary").insert(db_records_clean[i:i+chunk_size]).execute()
                
                st.cache_data.clear()
                st.sidebar.success(f"🎉 {upload_brand} ke liye {mp_type} ka data successfully refresh ho gaya!")
                st.rerun()
                
            except Exception as e:
                st.sidebar.error(f"Error aaya: {e}")

# --- Main Dashboard Brand Filtering View ---
st.markdown("## 📈 Brand, Marketplace & Month Wise Unified Reports")

if not df_design.empty:
    df_display = df_design.copy()
    
    # Map lowercase schema coming from Supabase cleanly
    if 'brand' not in df_display.columns and 'Brand' in df_display.columns:
        df_display = df_display.rename(columns={'Brand': 'brand', 'Month': 'month', 'Marketplace': 'marketplace', 'Design': 'design'})
    
    if 'brand' not in df_display.columns:
        df_display['brand'] = 'TERRADESI'
        
    # --- Top Level Dropdown Filters ---
    c1, c2, c3 = st.columns(3)
    with c1:
        unique_brands = list(df_display['brand'].dropna().unique())
        selected_brand = st.selectbox("⭐ Select Brand:", unique_brands if unique_brands else ["TERRADESI"])
    with c2:
        df_brand_filtered = df_display[df_display['brand'] == selected_brand]
        unique_mps = ["All"] + list(df_brand_filtered['marketplace'].dropna().unique())
        selected_mp = st.selectbox("Filter Marketplace:", unique_mps)
    with c3:
        unique_months = ["All"] + list(df_brand_filtered['month'].dropna().unique())
        selected_month = st.selectbox("Filter Month:", unique_months)
        
    # Apply Filtering
    df_final = df_brand_filtered.copy()
    if selected_mp != "All": 
        df_final = df_final[df_final['marketplace'] == selected_mp]
    if selected_month != "All": 
        df_final = df_final[df_final['month'] == selected_month]
        
    # Ensure columns exist and contain numerical float types
    num_cols = ['sale_amount', 'return_amount', 'marketplace_fee', 'del_qty', 'dto_qty', 'rto_qty', 'actual_qty', 'add_fees', 'settlement_amount']
    for col in num_cols:
        if col in df_final.columns:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0.0)
        else:
            df_final[col] = 0.0

    # UI Column Renaming for display match
    df_ui = df_final.rename(columns={
        'month': 'Month', 'marketplace': 'Marketplace', 'brand': 'Brand', 'design': 'Design',
        'sale_amount': 'Sale Amount', 'return_amount': 'Return Amount',
        'marketplace_fee': 'Marketplace Fees', 'del_qty': 'DEL QTY',
        'dto_qty': 'DTO QTY', 'rto_qty': 'RTO QTY', 'actual_qty': 'ACTUAL DEL QTY',
        'add_fees': 'ADD', 'settlement_amount': 'Settlement Amount'
    })
    
    # KPI Section
    st.markdown(f"### 📊 Quick KPI Summary for **{selected_brand}**")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Sales", f"₹{df_ui['Sale Amount'].sum():,.2f}")
    kpi2.metric("Total Settlement", f"₹{df_ui['Settlement Amount'].sum():,.2f}")
    kpi3.metric("DEL QTY (Actual)", f"{int(df_ui['ACTUAL DEL QTY'].sum()):,} Pcs")
    kpi4.metric("Total Return QTY", f"{int(df_ui['DTO QTY'].sum() + df_ui['RTO QTY'].sum()):,} Pcs")

    st.write("---")
    
    # --- Grid View Display ---
    st.subheader(f"📋 Live Ledger Data: {selected_brand}")
    
    fmt = {
        'Sale Amount': '₹{:,.2f}', 'Return Amount': '₹{:,.2f}', 'Marketplace Fees': '₹{:,.2f}',
        'ADD': '₹{:,.2f}', 'Settlement Amount': '₹{:,.2f}',
        'DEL QTY': '{:,.0f}', 'DTO QTY': '{:,.0f}', 'RTO QTY': '{:,.0f}', 'ACTUAL DEL QTY': '{:,.0f}'
    }
    
    st.dataframe(df_ui.style.format(fmt), use_container_width=True, hide_index=True)
    
    st.download_button(
        label=f"📥 Download Report ({selected_brand})",
        data=df_ui.to_csv(index=False).encode('utf-8'),
        file_name=f'{selected_brand}_Summary_Report.csv',
        mime='text/csv'
    )
else:
    st.info("Database abhi khali hai. Side panel se Brand Name aur Sheet select karke upload karein.")
