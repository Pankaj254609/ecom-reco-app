import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client

# --- Page Config ---
st.set_page_config(page_title="E-commerce Unified Dashboard", layout="wide")
st.title("📊 E-commerce Unified Design & Month-Wise Summary")

# --- Supabase Database Connection ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Supabase configuration secrets sahi nahi hain. Kripya check karein.")

# --- Load Cloud Data ---
@st.cache_data(ttl=600)
def load_cloud_data():
    try:
        res = supabase.table("design_wise_summary").select("*").limit(10000).execute()
        df = pd.DataFrame(res.data)
        return df
    except Exception as e:
        return pd.DataFrame()

df_design = load_cloud_data()

# --- Functions to Process Individual Marketplace Sheets ---
def process_flipkart(df):
    # Mapping columns
    df['Month'] = df['Payment Date'].fillna('')
    df['Marketplace'] = 'FLIPKART'
    
    # Status count logic based on Return Type
    df['DEL_QTY'] = np.where(df['Return Type'].str.upper() == 'DEL', df['Quantity'], 0)
    df['DTO_QTY'] = np.where(df['Return Type'].str.upper() == 'DTO', df['Quantity'], 0)
    df['RTO_QTY'] = np.where(df['Return Type'].str.upper() == 'RTO', df['Quantity'], 0)
    df['ACTUAL_QTY'] = np.where(df['Return Type'].str.upper() == 'DEL', df['Quantity'], 0)
    
    # Financial columns
    df['Sale Amount'] = pd.to_numeric(df['Sale Amount'], errors='coerce').fillna(0)
    df['Return Amount'] = pd.to_numeric(df['Refund (Rs.)'], errors='coerce').fillna(0)
    df['Marketplace Fee'] = pd.to_numeric(df['Marketplace Fee'], errors='coerce').fillna(0) + pd.to_numeric(df['Taxes (Rs.)'], errors='coerce').fillna(0)
    df['ADD_FEES'] = pd.to_numeric(df['Settlement Value ADD'], errors='coerce').fillna(0)
    df['Settlement Amount'] = pd.to_numeric(df['Bank Settlement'], errors='coerce').fillna(0)
    
    return df[['Month', 'Marketplace', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']]

def process_meesho(df):
    df['Month'] = df['Payment Date'].fillna('')
    df['Marketplace'] = 'MEESHO'
    
    # Status mapping
    status_col = 'Live Order Status' if 'Live Order Status' in df.columns else 'Status'
    df['DEL_QTY'] = np.where(df[status_col].str.upper() == 'DEL', df['QTY'], 0)
    df['DTO_QTY'] = np.where(df[status_col].str.upper() == 'DTO', df['QTY'], 0)
    df['RTO_QTY'] = np.where(df[status_col].str.upper() == 'RTO', df['QTY'], 0)
    df['ACTUAL_QTY'] = np.where(df[status_col].str.upper() == 'DEL', df['QTY'], 0)
    
    df['Sale Amount'] = pd.to_numeric(df['Total Sale Amount (Incl. Shipping & GST)'], errors='coerce').fillna(0)
    df['Return Amount'] = pd.to_numeric(df['Total Sale Return Amount'], errors='coerce').fillna(0)
    df['Marketplace Fee'] = pd.to_numeric(df['total comission'], errors='coerce').fillna(0)
    df['ADD_FEES'] = pd.to_numeric(df['ADD'], errors='coerce').fillna(0) if 'ADD' in df.columns else 0
    df['Settlement Amount'] = pd.to_numeric(df['Final Settlement Amount'], errors='coerce').fillna(0)
    
    return df[['Month', 'Marketplace', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']]

def process_amazon(df):
    df['Marketplace'] = 'AMAZON'
    df['DESIGN'] = df['DESIGN'].fillna('UNKNOWN')
    
    # Amazon has rows for TYPE (DEL, DTO, FEES, etc.)
    df['DEL_QTY'] = np.where(df['TYPE'].str.upper() == 'DEL', df['quantity'], 0)
    df['DTO_QTY'] = np.where(df['TYPE'].str.upper() == 'DTO', df['quantity'], 0)
    df['RTO_QTY'] = np.where(df['TYPE'].str.upper() == 'RTO', df['quantity'], 0)
    df['ACTUAL_QTY'] = np.where(df['TYPE'].str.upper() == 'DEL', df['quantity'], 0)
    
    df['Sale Amount'] = np.where(df['TYPE'].str.upper() == 'DEL', pd.to_numeric(df['product sales'], errors='coerce').fillna(0), 0)
    df['Return Amount'] = np.where(df['TYPE'].str.upper().isin(['RTO','DTO']), pd.to_numeric(df['product sales'], errors='coerce').fillna(0), 0)
    df['Marketplace Fee'] = np.where(df['TYPE'].str.upper() == 'FEES', pd.to_numeric(df['TOTAL'], errors='coerce').fillna(0), 0)
    df['ADD_FEES'] = np.where(df['TYPE'].str.upper() == 'ADD', pd.to_numeric(df['TOTAL'], errors='coerce').fillna(0), 0)
    df['Settlement Amount'] = pd.to_numeric(df['TOTAL'], errors='coerce').fillna(0)
    
    return df[['MONTH', 'Marketplace', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']].rename(columns={'MONTH': 'Month'})

def process_myntra(df):
    df['Marketplace'] = 'MYNTRA'
    
    df['DEL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    df['DTO_QTY'] = np.where(df['return_type'].str.upper() == 'DTO', df['QTY'], 0)
    df['RTO_QTY'] = np.where(df['return_type'].str.upper() == 'RTO', df['QTY'], 0)
    df['ACTUAL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    
    df['Sale Amount'] = pd.to_numeric(df['seller_product_amount'], errors='coerce').fillna(0)
    df['Return Amount'] = 0 # Calculate based on DTO/RTO logic if available
    df['Marketplace Fee'] = pd.to_numeric(df['total_commission_plus_tcs_tds_deduction'], errors='coerce').fillna(0)
    df['ADD_FEES'] = 0
    df['Settlement Amount'] = pd.to_numeric(df['total_actual_settlement'], errors='coerce').fillna(0)
    
    return df[['MONTH', 'Marketplace', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']].rename(columns={'MONTH': 'Month'})

def process_snapdeal(df):
    df['Marketplace'] = 'SNAPDEAL'
    
    df['DEL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    df['DTO_QTY'] = np.where(df['return_type'].str.upper() == 'DTO', df['QTY'], 0)
    df['RTO_QTY'] = np.where(df['return_type'].str.upper() == 'RTO', df['QTY'], 0)
    df['ACTUAL_QTY'] = np.where(df['return_type'].str.upper() == 'DEL', df['QTY'], 0)
    
    df['Sale Amount'] = pd.to_numeric(df['seller_product_amount'], errors='coerce').fillna(0)
    df['Return Amount'] = 0
    df['Marketplace Fee'] = pd.to_numeric(df['total_Commission_plus_tcs_tds_deduction'], errors='coerce').fillna(0)
    df['ADD_FEES'] = pd.to_numeric(df['ADD'], errors='coerce').fillna(0)
    df['Settlement Amount'] = pd.to_numeric(df['Settled'], errors='coerce').fillna(0)
    
    return df[['MONTH', 'Marketplace', 'DESIGN', 'Sale Amount', 'Return Amount', 'Marketplace Fee', 'DEL_QTY', 'DTO_QTY', 'RTO_QTY', 'ACTUAL_QTY', 'ADD_FEES', 'Settlement Amount']].rename(columns={'MONTH': 'Month'})


# --- Sidebar: File Upload Panel ---
st.sidebar.markdown("## 📤 Setteled Sheets Upload")
mp_type = st.sidebar.selectbox("Marketplace Select Karein:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA", "SNAPDEAL"])
uploaded_file = st.sidebar.file_uploader(f"{mp_type} Ki Sheet Upload Karein", type=["xlsx", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Process & Generate Summary"):
        with st.spinner("Sheet analyze aur calculate ho rahi hai..."):
            try:
                # Read CSV or Excel
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file)
                else:
                    df_raw = pd.read_excel(uploaded_file)
                
                # Standardize column casing and spacing
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                
                # Run respective channel processor
                if mp_type == "FLIPKART": df_processed = process_flipkart(df_raw)
                elif mp_type == "MEESHO": df_processed = process_meesho(df_raw)
                elif mp_type == "AMAZON": df_processed = process_amazon(df_raw)
                elif mp_type == "MYNTRA": df_processed = process_myntra(df_raw)
                elif mp_type == "SNAPDEAL": df_processed = process_snapdeal(df_raw)
                
                # Data cleaning
                df_processed = df_processed.dropna(subset=['DESIGN', 'Month'])
                df_processed = df_processed[df_processed['DESIGN'].astype(str).str.strip() != '']
                
                # --- AUTO-AGGREGATION (Design Wise + Month Wise Summary Calculation) ---
                summary_df = df_processed.groupby(['Month', 'Marketplace', 'DESIGN']).agg({
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
                
                # Push calculated summary to Database
                db_records = summary_df.to_dict(orientation='records')
                
                # Overwrite or Add logic
                supabase.table("design_wise_summary").delete().eq("marketplace", mp_type).execute()
                
                chunk_size = 200
                for i in range(0, len(db_records), chunk_size):
                    supabase.table("design_wise_summary").insert(db_records[i:i+chunk_size]).execute()
                
                st.cache_data.clear()
                st.sidebar.success(f"🎉 {mp_type} Ka Data successfully process aur design-wise update ho gaya!")
                st.rerun()
                
            except Exception as e:
                st.sidebar.error(f"Error aaya: {e}")

# --- Main Dashboard Summary View ---
st.markdown("## 📈 Design-wise & Month-wise Live Reports")

if not df_design.empty:
    # Quick Summary Calculation for UI
    df_display = df_design.copy()
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        selected_mp = st.selectbox("Filter Marketplace:", ["All"] + list(df_display['marketplace'].unique()))
    with col2:
        selected_month = st.selectbox("Filter Month:", ["All"] + list(df_display['month'].unique()))
        
    if selected_mp != "All": df_display = df_display[df_display['marketplace'] == selected_mp]
    if selected_month != "All": df_display = df_display[df_display['month'] == selected_month]
    
    # Formatting Columns for beautiful ledger view
    df_display = df_display.rename(columns={
        'month': 'Month', 'marketplace': 'Marketplace', 'design': 'Design',
        'sale_amount': 'Sale Amount', 'return_amount': 'Return Amount',
        'marketplace_fee': 'Marketplace Fees', 'del_qty': 'DEL QTY',
        'dto_qty': 'DTO QTY', 'rto_qty': 'RTO QTY', 'actual_qty': 'ACTUAL DEL QTY',
        'add_fees': 'ADD', 'settlement_amount': 'Settlement Amount'
    })
    
    # Add Total Month/Design rows using pandas Pivot or grouping inside the app if needed
    st.subheader("📋 Final Aggregated Ledger View")
    
    # Formatting styles
    fmt = {
        'Sale Amount': '₹{:,.2f}', 'Return Amount': '₹{:,.2f}', 'Marketplace Fees': '₹{:,.2f}',
        'ADD': '₹{:,.2f}', 'Settlement Amount': '₹{:,.2f}',
        'DEL QTY': '{:,.0f}', 'DTO QTY': '{:,.0f}', 'RTO QTY': '{:,.0f}', 'ACTUAL DEL QTY': '{:,.0f}'
    }
    
    st.dataframe(df_display.style.format(fmt), use_container_width=True, hide_index=True)
    
    # Download report
    st.download_button(
        label="📥 Download Summary Report",
        data=df_display.to_csv(index=False).encode('utf-8'),
        file_name='Design_Month_Wise_Summary.csv',
        mime='text/csv'
    )
else:
    st.info("Database abhi khali hai. Side panel se kisi bhi channel ki settlement sheet upload karein.")
