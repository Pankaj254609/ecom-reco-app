import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client

# --- Page Config ---
st.set_page_config(page_title="Multi-Brand E-commerce Dashboard", layout="wide")
st.title("📊 डिज़ाइन-वाइज़, मंथ-वाइज़ और ब्रांड-वाइज़ ओवरऑल समरी डैशबोर्ड")

# --- Custom Global UI Styling (Uniform #46bdc6 Color Style) ---
st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        background-color: #46bdc6 !important;
        padding: 15px !important;
        border-radius: 8px !important;
        border: 1px solid #3197a0 !important;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        color: black !important;
    }
    div[data-testid="stDataFrame"] table th {
        background-color: #46bdc6 !important;
        color: black !important;
        font-weight: bold !important;
        border: 1px solid #3197a0 !important;
        text-align: center !important;
    }
    div[data-testid="stDataFrame"] table td {
        border: 1px solid #3197a0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Direct Supabase Database Connection ---
@st.cache_resource
def init_supabase() -> Client:
    url = "https://tpbbngotolgthytgjarp.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwYmJuZ290b2xndGh5dGdqYXJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM3MzY3NTMsImV4cCI6MjA5OTMxMjc1M30.0uxeXOsMDbAjtAdT_RZlb6NAs-OBlydKr13-lv9l5Lw"
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Supabase connection error: {e}")
    st.stop()

# --- Helper to Clean Numbers ---
def get_num_val(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).replace('₹', '').replace(',', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0

# --- ADVANCED FLIPKART SKU & ORDER ITEM ID PROCESSOR ---
def process_flipkart_sku_wise(df, brand_name):
    # Strip whitespaces from columns
    df.columns = [str(c).strip() for c in df.columns]
    
    # 1. Clean the essential numeric columns first
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0).astype(int)
    df['Sale Amount (Rs.)'] = df['Sale Amount (Rs.)'].apply(get_num_val)
    df['Refund (Rs.)'] = df['Refund (Rs.)'].apply(get_num_val)
    df['Marketplace Fee (Rs.)'] = df['Marketplace Fee (Rs.)'].apply(get_num_val)
    df['Taxes (Rs.)'] = df['Taxes (Rs.)'].apply(get_num_val)
    
    # Optional Columns Handling safely
    add_col = 'Settlement Value ADD' if 'Settlement Value ADD' in df.columns else 'Offer Adjustments (Rs.)'
    df['ADD_VAL'] = df[add_col].apply(get_num_val) if add_col in df.columns else 0.0
    df['Bank Settlement'] = df['Bank Settlement Value (Rs.)'].apply(get_num_val) if 'Bank Settlement Value (Rs.)' in df.columns else 0.0
    
    # 2. Identify Return Categories accurately based on 'Return Type' status
    df['Return Type'] = df['Return Type'].fillna('NA').astype(str).str.strip().str.upper()
    
    # Logic for counting real pieces/orders status wise
    df['Is_Sale'] = np.where((df['Return Type'] == 'NA') & (df['Quantity'] > 0), df['Quantity'], 0)
    df['Logistics_Return'] = np.where(df['Return Type'].str.contains('RTO|DTO|COURIER', case=False, na=False), df['Quantity'], 0)
    df['Customer_Return'] = np.where(df['Return Type'].str.contains('CUSTOMER', case=False, na=False), df['Quantity'], 0)
    
    # 3. Aggregating data at unique Order Item ID + SKU Level to resolve 0-180 row problem
    groupby_cols = ['Order item ID', 'Seller SKU'] if 'Seller SKU' in df.columns else ['Order item ID', 'Order ID']
    
    sku_summary = df.groupby(groupby_cols).agg({
        'Is_Sale': 'sum',
        'Logistics_Return': 'sum',
        'Customer_Return': 'sum',
        'Sale Amount (Rs.)': 'sum',
        'Refund (Rs.)': 'sum',
        'Marketplace Fee (Rs.)': 'sum',
        'Taxes (Rs.)': 'sum',
        'ADD_VAL': 'sum',
        'Bank Settlement': 'sum'
    }).reset_index()
    
    # Rename columns to provide absolute clarity
    sku_summary.columns = [
        'Order Item ID', 'Seller SKU', 'Total Sale Qty', 'Total Logistics Return Qty', 
        'Total Customer Return Qty', 'Gross Sale Amt', 'Total Refund', 
        'Marketplace Fees', 'Taxes', 'Total ADD Fees', 'Net Settled Amount'
    ]
    
    return sku_summary

# --- Sidebar Uploading Panel ---
st.sidebar.markdown("## 📤 Sheet Upload & Management")
upload_brand = st.sidebar.text_input("Brand Name Likhein:", "RECOAPPPY").strip().upper()
mp_type = st.sidebar.selectbox("Marketplace Select Karein:", ["FLIPKART", "AMAZON", "MEESHO"])
uploaded_file = st.sidebar.file_uploader(f"{mp_type} Ki Sheet Upload Karein", type=["xlsx", "csv"])

# --- Main Logic Dashboard ---
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, low_memory=False)
        else:
            df_raw = pd.read_excel(uploaded_file)
            
        st.success("File uploaded successfully! Processing details...")
        
        if mp_type == "FLIPKART":
            # Running the dedicated item-sku tracker
            processed_report = process_flipkart_sku_wise(df_raw, upload_brand)
            
            # Show Metrics Row
            st.markdown(f"### 📈 SKU-Wise Summary Report Overview ({upload_brand})")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Gross Sales", f"₹{processed_report['Gross Sale Amt'].sum():,.2f}")
            k2.metric("Net Settled Amount", f"₹{processed_report['Net Settled Amount'].sum():,.2f}")
            k3.metric("Total Logistics Return Pcs", f"{int(processed_report['Total Logistics Return Qty'].sum())} Pcs")
            k4.metric("Total Customer Return Pcs", f"{int(processed_report['Total Customer Return Qty'].sum())} Pcs")
            
            st.write("---")
            
            # Add TOTAL row at the bottom of the table
            total_row = pd.DataFrame([{
                'Order Item ID': 'TOTAL', 'Seller SKU': '',
                'Total Sale Qty': processed_report['Total Sale Qty'].sum(),
                'Total Logistics Return Qty': processed_report['Total Logistics Return Qty'].sum(),
                'Total Customer Return Qty': processed_report['Total Customer Return Qty'].sum(),
                'Gross Sale Amt': processed_report['Gross Sale Amt'].sum(),
                'Total Refund': processed_report['Total Refund'].sum(),
                'Marketplace Fees': processed_report['Marketplace Fees'].sum(),
                'Taxes': processed_report['Taxes'].sum(),
                'Total ADD Fees': processed_report['Total ADD Fees'].sum(),
                'Net Settled Amount': processed_report['Net Settled Amount'].sum()
            }])
            
            display_df = pd.concat([processed_report, total_row], ignore_index=True)
            
            # Dynamic Uniform #46bdc6 Table Formatter
            def style_full_table(df):
                return df.style.apply(lambda x: pd.DataFrame([['background-color: #46bdc6; color: black; font-weight: bold;'] * len(df.columns)], index=df.index, columns=df.columns), axis=None)
            
            fmt = {
                'Gross Sale Amt': '₹{:,.2f}', 'Total Refund': '₹{:,.2f}', 'Marketplace Fees': '₹{:,.2f}',
                'Taxes': '₹{:,.2f}', 'Total ADD Fees': '₹{:,.2f}', 'Net Settled Amount': '₹{:,.2f}'
            }
            
            styled_final = style_full_table(display_df).format(fmt)
            
            # Display live grid
            st.subheader("📋 Live Order Item ID & SKU Wise Consolidated Sheet")
            st.dataframe(styled_final, use_container_width=True, hide_index=True)
            
            # Download report button
            st.download_button(
                label="📥 Download This SKU Wise Settled Report",
                data=processed_report.to_csv(index=False).encode('utf-8'),
                file_name=f'{upload_brand}_SKU_Wise_Settlement.csv',
                mime='text/csv'
            )
        else:
            st.info("Kripya Flipkart select karein is absolute item mapping ko dekhne ke liye.")
            
    except Exception as e:
        st.error(f"Processing error: {str(e)}")
else:
    st.info("Kripya side panel se apni Flipkart ki 'Orders' sheet upload karein taaki data calculate kiya ja sake.")
