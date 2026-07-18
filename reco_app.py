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
        .metric-card {
            background-color: #1e293b;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
            text-align: center;
            border: 1px solid #334155;
            margin-bottom: 15px;
        }
        .metric-title {
            font-size: 14px;
            color: #94a3b8;
            font-weight: 600;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 20px;
            color: #f8fafc;
            font-weight: bold;
        }
        .stButton>button {
            width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Design-Wise Financial Summary Dashboard")

# --- 🎯 PERMANENT MEMORY SETUP ---
if 'final_summary_df' not in st.session_state:
    st.session_state['final_summary_df'] = None
if 'saved_ads_amount' not in st.session_state:
    st.session_state['saved_ads_amount'] = 0.0

# Database Columns Check
db_columns = []
try:
    inspect_query = supabase.table("design_wise_summary").select("*").limit(1).execute()
    if inspect_query.data:
        db_columns = [col.lower().strip() for col in inspect_query.data[0].keys()]
except Exception:
    pass

if not db_columns:
    db_columns = ["brand", "marketplace", "design", "gross_sale_amt", "total_refund", "marketplace_fees", "total_add_fees", "net_settled_amount", "total_sale_pcs", "sale_qty", "logistics_return_pcs", "logistics_return_qty", "customer_return_pcs", "customer_return_qty", "month", "month_year"]

# ==========================================
# STEP 1: UPLOAD & PROCESS ZONE
# ==========================================
st.markdown("### 📤 Step 1: Data Processing Panel")
up_col1, up_col2, up_col3 = st.columns([1, 1, 2])

with up_col1:
    upload_brand = st.text_input("Brand Name:", "VIDA LOCA").strip().upper()
    upload_mp = st.selectbox("Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])

with up_col2:
    manual_ads_value = st.number_input("💵 Total Ads Cost (From Excel):", min_value=0.0, value=0.0, step=100.0)
    upload_month = st.text_input("Month/Year (e.g., JAN_26):", "JAN_26").strip().upper()

with up_col3:
    uploaded_file = st.file_uploader("Choose Excel File (.xlsx)", type=["xlsx"])

# Excel file reading logic
if uploaded_file is not None:
    try:
        file_bytes = uploaded_file.read()
        xls_file = pd.ExcelFile(io.BytesIO(file_bytes))
        orders_sheet = 'Orders' if 'Orders' in xls_file.sheet_names else xls_file.sheet_names[0]
        df_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=orders_sheet)
        
        target_keywords = ['sku', 'seller sku', 'sale amount', 'my share', 'refund']
        for i in range(min(15, df_raw.shape[0])):
            row_str_vals = [str(x).lower().strip() for x in df_raw.iloc[i].values]
            if any(k in row_str_vals for k in target_keywords):
                df_raw.columns = df_raw.iloc[i]
                df_raw = df_raw[i+1:].reset_index(drop=True)
                break
        
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        all_file_cols = list(df_raw.columns)
        
        def get_default_idx(lst, keywords):
            for kw in keywords:
                for idx, col in enumerate(lst):
                    if kw.lower() in str(col).lower():
                        return idx
            return 0

        st.info("🎯 Review sheet column mappings below:")
        c_map1, c_map2, c_map3 = st.columns(3)
        with c_map1:
            design_col = st.selectbox("SKU Column:", all_file_cols, index=get_default_idx(all_file_cols, ["seller sku", "sku", "design"]))
            gross_sale_col = st.selectbox("Sales Column:", all_file_cols, index=get_default_idx(all_file_cols, ["sale amount total", "gross sales", "sale amount"]))
        with c_map2:
            refund_col = st.selectbox("Refund Column:", all_file_cols, index=get_default_idx(all_file_cols, ["refund"]))
            mp_fees_col = st.selectbox("Fees Column:", all_file_cols, index=get_default_idx(all_file_cols, ["marketplace fee", "fees", "fee"]))
        with c_map3:
            net_settled_col = st.selectbox("Net Settled Column:", all_file_cols, index=get_default_idx(all_file_cols, ["my share", "net settled"]))
            qty_col = st.selectbox("Qty Column:", all_file_cols, index=get_default_idx(all_file_cols, ["quantity", "qty"]))
            
        return_status_col = st.selectbox("Return Status (Optional):", ["None"] + all_file_cols, index=get_default_idx(["None"] + all_file_cols, ["return type", "status"]))

        # Data Cleaning
        df_raw[design_col] = df_raw[design_col].astype(str).str.strip().str.upper()
        df_raw['Clean_Qty'] = pd.to_numeric(df_raw[qty_col], errors='coerce').fillna(0).astype(int)
        
        if return_status_col != "None":
            df_raw['Temp_Status'] = df_raw[return_status_col].astype(str).str.strip().str.lower().fillna('na')
            df_raw['Logistics_Return'] = np.where(df_raw['Temp_Status'].str.contains('logistics return|forward verification', na=False), df_raw['Clean_Qty'], 0)
            df_raw['Customer_Return'] = np.where(df_raw['Temp_Status'].str.contains('customer return', na=False), df_raw['Clean_Qty'], 0)
            df_raw['Is_Sale'] = np.where((df_raw['Logistics_Return'] == 0) & (df_raw['Customer_Return'] == 0), df_raw['Clean_Qty'], 0)
        else:
            df_raw['Is_Sale'] = df_raw['Clean_Qty']
            df_raw['Logistics_Return'] = 0
            df_raw['Customer_Return'] = 0

        def clean_numeric_series(col_n):
            s = df_raw[col_n].astype(str).str.replace('₹', '', regex=False).str.replace(',', '', regex=False).str.strip()
            return pd.to_numeric(s, errors='coerce').fillna(0)

        df_raw['Gross_Sale_Clean'] = clean_numeric_series(gross_sale_col)
        df_raw['Refund_Clean'] = clean_numeric_series(refund_col)
        df_raw['Fees_Clean'] = clean_numeric_series(mp_fees_col)
        df_raw['Net_Settled_Clean'] = clean_numeric_series(net_settled_col)

        summary_df = df_raw.groupby(design_col).agg({
            'Gross_Sale_Clean': 'sum',
            'Refund_Clean': 'sum',
            'Fees_Clean': 'sum',
            'Net_Settled_Clean': 'sum',
            'Is_Sale': 'sum',
            'Logistics_Return': 'sum',
            'Customer_Return': 'sum'
        }).reset_index()
        
        summary_df.columns = ['design', 'gross_sale_amt', 'total_refund', 'marketplace_fees', 'net_settled_amount', 'total_sale_pcs', 'logistics_return_pcs', 'customer_return_pcs']
        
        # 🎯 Lock into permanent state memory
        st.session_state['final_summary_df'] = summary_df
        st.session_state['saved_ads_amount'] = float(manual_ads_value)

    except Exception as e:
        st.error(f"Error parsing sheet structure: {str(e)}")

# --- UPLOAD TO DATABASE BUTTON ---
if st.session_state['final_summary_df'] is not None:
    if st.button("🚀 Process & Upload All Data to Supabase Cloud"):
        df_to_upload = st.session_state['final_summary_df'].copy()
        total_ads = st.session_state['saved_ads_amount']
        
        # Split ads dynamic allocation per design
        unique_designs = len(df_to_upload)
        df_to_upload['total_add_fees'] = total_ads / unique_designs if unique_designs > 0 else 0.0
        
        db_payload = []
        for _, row in df_to_upload.iterrows():
            item = {
                "brand": upload_brand, "marketplace": upload_mp, "design": str(row['design']),
                "gross_sale_amt": float(row['gross_sale_amt']), "total_refund": float(row['total_refund']),
                "marketplace_fees": float(row['marketplace_fees']), "total_add_fees": float(row['total_add_fees']),
                "net_settled_amount": float(row['net_settled_amount']), "total_sale_pcs": int(row['total_sale_pcs']),
                "sale_qty": int(row['total_sale_pcs']), "logistics_return_pcs": int(row['logistics_return_pcs']),
                "logistics_return_qty": int(row['logistics_return_pcs']), "customer_return_pcs": int(row['customer_return_pcs']),
                "customer_return_qty": int(row['customer_return_pcs']), "month": upload_month, "month_year": upload_month
            }
            db_payload.append({k: v for k, v in item.items() if k in db_columns})

        if db_payload:
            try:
                supabase.table("design_wise_summary").delete().eq("marketplace", upload_mp).eq("brand", upload_brand).eq("month", upload_month).execute()
            except Exception: pass
            
            supabase.table("design_wise_summary").insert(db_payload).execute()
            st.success(f"🎉 Success! Cloud updated with ₹ {total_ads:,.2f} Ads Amount!")
            st.balloons()

st.markdown("---")

# ==========================================
# STEP 2: RENDER LIVE DASHBOARD METRICS
# ==========================================
st.markdown("### 📊 Step 2: Live Financial Summary Analytics")

display_df = None
if st.session_state['final_summary_df'] is not None:
    display_df = st.session_state['final_summary_df'].copy()
    total_ads_to_show = st.session_state['saved_ads_amount']
    # Split for preview grid
    display_df['total_add_fees'] = total_ads_to_show / len(display_df) if len(display_df) > 0 else 0.0
else:
    # Database Fallback if no fresh upload in session state
    try:
        query_res = supabase.table("design_wise_summary").select("*").execute()
        if query_res.data:
            display_df = pd.DataFrame(query_res.data)
            display_df['total_add_fees'] = pd.to_numeric(display_df.get('total_add_fees', 0), errors='coerce').fillna(0)
            total_ads_to_show = display_df['total_add_fees'].sum()
    except Exception:
        pass

if display_df is not None and len(display_df) > 0:
    # Force data type clean conversion
    for money_col in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'net_settled_amount']:
        if money_col in display_df.columns:
            display_df[money_col] = pd.to_numeric(display_df[money_col], errors='coerce').fillna(0)

    s_gross = display_df['gross_sale_amt'].sum() if 'gross_sale_amt' in display_df.columns else 0.0
    s_refund = display_df['total_refund'].sum() if 'total_refund' in display_df.columns else 0.0
    s_fees = display_df['marketplace_fees'].sum() if 'marketplace_fees' in display_df.columns else 0.0
    s_net = display_df['net_settled_amount'].sum() if 'net_settled_amount' in display_df.columns else 0.0

    # UI Card Layout
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-title">Gross Sales</div><div class="metric-value">₹ {s_gross:,.2f}</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card"><div class="metric-title">Total Refund</div><div class="metric-value">₹ {s_refund:,.2f}</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-title">Marketplace Fees</div><div class="metric-value">₹ {s_fees:,.2f}</div></div>', unsafe_allow_html=True)
    
    # 🎯 FIX CONFIRMED: Direct injection of state tracking
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-title">Total ADD Fees (Ads)</div><div class="metric-value">₹ {total_ads_to_show:,.2f}</div></div>', unsafe_allow_html=True)
    
    with m5: st.markdown(f'<div class="metric-card"><div class="metric-title">Net Settled</div><div class="metric-value">₹ {s_net:,.2f}</div></div>', unsafe_allow_html=True)

    # Breakdown Grid View
    st.subheader("📋 Detailed Design Breakdown Grid")
    grid_df = display_df.copy()
    for c in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'total_add_fees', 'net_settled_amount']:
        if c in grid_df.columns:
            grid_df[c] = grid_df[c].apply(lambda x: f"₹ {x:,.2f}")
    st.dataframe(grid_df, use_container_width=True)
else:
    st.info("👋 System Idle. Drag and drop your spreadsheet into Step 1 above to initialize calculations.")
