import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client

# --- Page Config ---
st.set_page_config(page_title="VIDA LOCA RECO", layout="wide")
st.title("📊 VIDA LOCA RECO")

# --- Custom Global UI Styling (#46bdc6 Uniform Layout) ---
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
        font-weight: bold !important;
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
    st.error(f"Supabase Initialize Error: {e}")
    st.stop()

# --- Load Realtime Cloud Data ---
@st.cache_data(ttl=30)
def load_cloud_data():
    try:
        res = supabase.table("design_wise_summary").select("*").limit(25000).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Data pull errors: {e}")
        return pd.DataFrame()

df_db_raw = load_cloud_data()

# --- Helper to Parse Numbers ---
def get_num_val(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).replace('₹', '').replace(',', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0

# --- FLIPKART ADVANCED MAPPING & ROW SKIP ENGINE ---
def process_flipkart_raw(df, brand_name):
    # Skip any top comment/summary rows if present
    for i in range(min(20, len(df))):
        row_str = [str(x).lower().strip() for x in df.iloc[i].dropna().values]
        if any('order item id' in x or 'quantity' in x or 'sale amount' in x for x in row_str):
            df.columns = [str(c).strip() for c in df.iloc[i]]
            df = df.iloc[i+1:].reset_index(drop=True)
            break

    df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
    col_mapping = {c.lower(): c for c in df.columns}
    
    qty_col = next((col_mapping[k] for k in col_mapping if 'quantity' in k), None)
    sale_col = next((col_mapping[k] for k in col_mapping if 'sale amount' in k), None)
    refund_col = next((col_mapping[k] for k in col_mapping if 'refund' in k), None)
    fee_col = next((col_mapping[k] for k in col_mapping if 'marketplace fee' in k), None)
    add_col = next((col_mapping[k] for k in col_mapping if 'offer adjustment' in k or 'settlement value add' in k), None)
    settle_col = next((col_mapping[k] for k in col_mapping if 'bank settlement' in k or 'settled' in k), None)
    
    sku_col = next((col_mapping[k] for k in col_mapping if 'seller sku' in k or 'sku' in k), None)
    return_type_col = next((col_mapping[k] for k in col_mapping if 'return type' in k or 'return_type' in k), None)
    date_col = next((col_mapping[k] for k in col_mapping if 'payment date' in k or 'date' in k), None)

    if not qty_col or not sku_col:
        st.error("❌ 'Quantity' ya 'Seller SKU' column sheet mein nahi mila! Kripya sahi sheet tab select karein.")
        st.stop()

    # Create dynamic Month column
    if date_col:
        df['Month'] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%B-%Y').fillna('Unknown-Month')
    else:
        df['Month'] = 'Unknown-Month'

    df['Clean_Qty'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)
    df['Clean_Sale'] = df[sale_col].apply(get_num_val) if sale_col else 0.0
    df['Clean_Refund'] = df[refund_col].apply(get_num_val) if refund_col else 0.0
    df['Clean_Fee'] = df[fee_col].apply(get_num_val) if fee_col else 0.0
    df['Clean_Add'] = df[add_col].apply(get_num_val) if add_col else 0.0
    df['Clean_Settle'] = df[settle_col].apply(get_num_val) if settle_col else 0.0
    
    # Advanced Return categorization logic
    df['Temp_Return'] = df[return_type_col].fillna('NA').astype(str).str.strip().str.upper() if return_type_col else 'NA'
    
    df['Is_Sale'] = np.where(df['Temp_Return'] == 'NA', df['Clean_Qty'], 0)
    df['Logistics_Return'] = np.where(df['Temp_Return'].str.contains('RTO|DTO|COURIER', case=False, na=False), df['Clean_Qty'], 0)
    df['Customer_Return'] = np.where(df['Temp_Return'].str.contains('CUSTOMER', case=False, na=False), df['Clean_Qty'], 0)
    
    # Grouping by multi-dimensional entities
    summary = df.groupby(['Month', sku_col]).agg({
        'Is_Sale': 'sum',
        'Logistics_Return': 'sum',
        'Customer_Return': 'sum',
        'Clean_Sale': 'sum',
        'Clean_Refund': 'sum',
        'Clean_Fee': 'sum',
        'Clean_Add': 'sum',
        'Clean_Settle': 'sum'
    }).reset_index()
    
    summary.columns = [
        'month', 'design', 'sale_qty', 'logistics_return_qty', 'customer_return_qty',
        'sale_amount', 'return_amount', 'marketplace_fee', 'add_fees', 'settlement_amount'
    ]
    summary['marketplace'] = 'FLIPKART'
    summary['brand'] = brand_name
    
    return summary

# --- Sidebar Upload Panel ---
st.sidebar.markdown("## 📤 Cloud Data Sync Center")
upload_brand = st.sidebar.text_input("Brand Name:", "RECOAPPPY").strip().upper()
mp_type = st.sidebar.selectbox("Marketplace:", ["FLIPKART", "AMAZON", "MEESHO"])
uploaded_file = st.sidebar.file_uploader("Settle Payment Sheet Upload Karein", type=["csv", "xlsx"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Push to Database & Refresh Dashboard"):
        with st.spinner("Processing calculations..."):
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_raw = pd.read_csv(uploaded_file, low_memory=False)
                else:
                    xl = pd.ExcelFile(uploaded_file)
                    target = 'Orders' if 'Orders' in xl.sheet_names else xl.sheet_names[0]
                    df_raw = pd.read_excel(uploaded_file, sheet_name=target)
                
                if mp_type == "FLIPKART":
                    summary_df = process_flipkart_raw(df_raw, upload_brand)
                
                # Dynamic Safe Filter
                db_records = summary_df.to_dict(orient='records')
                
                # Delete existing entries safely
                try:
                    supabase.table("design_wise_summary").delete().eq("marketplace", mp_type).eq("brand", upload_brand).execute()
                except:
                    pass
                
                # Batch push to database safely
                chunk_size = 200
                for i in range(0, len(db_records), chunk_size):
                    row_data = db_records[i:i+chunk_size]
                    try:
                        supabase.table("design_wise_summary").insert(row_data).execute()
                    except Exception as ins_err:
                        st.sidebar.warning("⚠️ Database columns mismatch fallback activated.")
                        for r in row_data:
                            r.pop('customer_return_qty', None)
                            r.pop('logistics_return_qty', None)
                        supabase.table("design_wise_summary").insert(row_data).execute()
                
                st.cache_data.clear()
                st.sidebar.success("🎉 Database successfully synced!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error during push operation: {e}")

# --- Main Consolidated Dashboard Controls ---
st.markdown("## 🎯 Realtime Global Filters (Brand / Month / Marketplace)")

if not df_db_raw.empty:
    df_db_raw.columns = [c.lower() for c in df_db_raw.columns]
    df_db_raw['brand'] = df_db_raw['brand'].astype(str).str.upper().str.strip()
    
    # 3-Way Filters Row
    c1, c2, c3 = st.columns(3)
    with c1:
        unique_brands = sorted(list(df_db_raw['brand'].dropna().unique()))
        selected_brand = st.selectbox("⭐ Select Brand:", unique_brands)
    with c2:
        df_b_filtered = df_db_raw[df_db_raw['brand'] == selected_brand]
        unique_months = ["All"] + sorted(list(df_b_filtered['month'].dropna().unique()))
        selected_month = st.selectbox("📅 Select Month:", unique_months)
    with c3:
        unique_mps = ["All"] + sorted(list(df_b_filtered['marketplace'].dropna().unique()))
        selected_mp = st.selectbox("🌐 Select Marketplace:", unique_mps)
        
    df_final = df_b_filtered.copy()
    if selected_month != "All":
        df_final = df_final[df_final['month'] == selected_month]
    if selected_mp != "All":
        df_final = df_final[df_final['marketplace'] == selected_mp]
        
    # --- SAFE COLUMN CHECK LOGIC ---
    required_cols = {
        'sale_qty': 0, 'logistics_return_qty': 0, 'customer_return_qty': 0,
        'sale_amount': 0.0, 'return_amount': 0.0, 'marketplace_fee': 0.0, 
        'add_fees': 0.0, 'settlement_amount': 0.0
    }
    for rc, default_val in required_cols.items():
        if rc not in df_final.columns:
            df_final[rc] = default_val
            
    # Standardize types safely
    for col in required_cols.keys():
        df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0.0)

    # Aggregate consolidated views
    ui_report = df_final.groupby(['month', 'marketplace', 'brand', 'design']).agg({
        'sale_qty': 'sum',
        'logistics_return_qty': 'sum',
        'customer_return_qty': 'sum',
        'sale_amount': 'sum',
        'return_amount': 'sum',
        'marketplace_fee': 'sum',
        'add_fees': 'sum',
        'settlement_amount': 'sum'
    }).reset_index()

    # Rename columns to user friendly UI grid headers
    ui_report.columns = [
        'Month', 'Marketplace', 'Brand', 'Seller SKU / Design', 'Total Sale Pcs', 
        'Logistics Return Pcs', 'Customer Return Pcs', 'Gross Sale Amt', 
        'Total Refund', 'Marketplace Fees', 'Total ADD Fees', 'Net Settled Amount'
    ]

    # Global KPI sums
    sales_sum = ui_report['Gross Sale Amt'].sum()
    settle_sum = ui_report['Net Settled Amount'].sum()
    total_sale_pcs = ui_report['Total Sale Pcs'].sum()
    total_log_pcs = ui_report['Logistics Return Pcs'].sum()

    st.markdown(f"### 📈 Quick Metrics Summary for **{selected_brand}** ({selected_month} / {selected_mp})")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Gross Sales Value", f"₹{sales_sum:,.2f}")
    kpi2.metric("Net Bank Settled", f"₹{settle_sum:,.2f}")
    kpi3.metric("Total Sale Items Sold", f"{int(total_sale_pcs):,} Pcs")
    kpi4.metric("Total Logistic Returns", f"{int(total_log_pcs):,} Pcs")

    st.write("---")
    
    # Injecting Bottom Dynamic TOTAL Row
    total_row = pd.DataFrame([{
        'Month': 'TOTAL', 'Marketplace': '', 'Brand': '', 'Seller SKU / Design': '',
        'Total Sale Pcs': ui_report['Total Sale Pcs'].sum(),
        'Logistics Return Pcs': ui_report['Logistics Return Pcs'].sum(),
        'Customer Return Pcs': ui_report['Customer Return Pcs'].sum(),
        'Gross Sale Amt': ui_report['Gross Sale Amt'].sum(),
        'Total Refund': ui_report['Total Refund'].sum(),
        'Marketplace Fees': ui_report['Marketplace Fees'].sum(),
        'Total ADD Fees': ui_report['Total ADD Fees'].sum(),
        'Net Settled Amount': ui_report['Net Settled Amount'].sum()
    }])
    
    display_df = pd.concat([ui_report, total_row], ignore_index=True)

    def style_ledger_table(df):
        return df.style.apply(lambda x: pd.DataFrame([['background-color: #46bdc6; color: black; font-weight: bold;'] * len(df.columns)], index=df.index, columns=df.columns), axis=None)

    fmt_rules = {
        'Gross Sale Amt': '₹{:,.2f}', 'Total Refund': '₹{:,.2f}', 'Marketplace Fees': '₹{:,.2f}',
        'Total ADD Fees': '₹{:,.2f}', 'Net Settled Amount': '₹{:,.2f}',
        'Total Sale Pcs': '{:,.0f}', 'Logistics Return Pcs': '{:,.0f}', 'Customer Return Pcs': '{:,.0f}'
    }
    
    styled_df = style_ledger_table(display_df).format(fmt_rules)
    
    st.subheader(f"📋 Live Consolidated Ledger Matrix: {selected_brand}")
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.download_button(
        label=f"📥 Download Report ({selected_brand})",
        data=ui_report.to_csv(index=False).encode('utf-8'),
        file_name=f'{selected_brand}_Consolidated_Report.csv',
        mime='text/csv'
    )
else:
    st.info("Database khali hai ya dynamic pull response waiting me h. Kripya side panel se main sheet upload karke database refresh karein.")
