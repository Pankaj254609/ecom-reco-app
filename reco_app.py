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

# Fetch Dynamic Database Columns
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
# STEP 1: UPLOAD & PROCESS ZONE (Top Panel)
# ==========================================
st.markdown("### 📤 Step 1: Upload Report & Enter Manual Costs")
up_col1, up_col2, up_col3 = st.columns([1, 1, 2])

with up_col1:
    upload_brand = st.text_input("Brand Name:", "VIDA LOCA").strip().upper()
    upload_mp = st.selectbox("Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])

with up_col2:
    # 🎯 MANUAL ADS INPUT BOX (Direct Variable Mapping)
    manual_ads_value = st.number_input("💵 Total Ads Cost (From Excel):", min_value=0.0, value=0.0, step=100.0, key="direct_ads_input")
    upload_month = st.text_input("Month/Year (e.g., JAN_26):", "JAN_26").strip().upper()

with up_col3:
    uploaded_file = st.file_uploader("Choose Excel File (.xlsx)", type=["xlsx"])

processed_df = None

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

        # Mapping Columns Safely
        st.info("💡 Confirm sheet structure below if numbers look mismatched:")
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

        # Calculations
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

        processed_df = df_raw.groupby(design_col).agg({
            'Gross_Sale_Clean': 'sum',
            'Refund_Clean': 'sum',
            'Fees_Clean': 'sum',
            'Net_Settled_Clean': 'sum',
            'Is_Sale': 'sum',
            'Logistics_Return': 'sum',
            'Customer_Return': 'sum'
        }).reset_index()
        
        processed_df.columns = ['design', 'gross_sale_amt', 'total_refund', 'marketplace_fees', 'net_settled_amount', 'total_sale_pcs', 'logistics_return_pcs', 'customer_return_pcs']

        # Inject Manual Ads Value straight to memory dataframe
        unique_designs = len(processed_df)
        if unique_designs > 0:
            processed_df['total_add_fees'] = manual_ads_value / unique_designs
        else:
            processed_df['total_add_fees'] = 0.0

        # Save to Cloud Action
        if st.button("🚀 Confirm & Upload Data to Supabase"):
            db_payload = []
            for _, row in processed_df.iterrows():
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
                st.success("🎉 Database successfully updated!")
                st.balloons()

    except Exception as e:
        st.error(f"Error reading file structure: {str(e)}")

st.markdown("---")

# ==========================================
# STEP 2: DYNAMIC LIVE DASHBOARD
# ==========================================
st.markdown("### 📊 Step 2: Live Financial Analytics Summary")

# Base source prioritization: Agar abhi file upload kari hai to live check hoga, varna database backup uthayega.
final_df = None
source_label = ""

if processed_df is not None:
    final_df = processed_df.copy()
    source_label = "Showing Unsaved Live Preview (Based on uploaded file + manual input)"
else:
    try:
        query_res = supabase.table("design_wise_summary").select("*").execute()
        if query_res.data:
            final_df = pd.DataFrame(query_res.data)
            source_label = f"Showing Saved Records from Database Cloud"
    except Exception:
        pass

if final_df is not None and len(final_df) > 0:
    st.caption(f"ℹ️ Status: *{source_label}*")
    
    # Type cast data series safely
    for money_col in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'net_settled_amount']:
        if money_col in final_df.columns:
            final_df[money_col] = pd.to_numeric(final_df[money_col], errors='coerce').fillna(0)
            
    # Direct Force Compute for Ads Value
    if 'total_add_fees' in final_df.columns:
        final_df['total_add_fees'] = pd.to_numeric(final_df['total_add_fees'], errors='coerce').fillna(0)
        # Check condition: Agar database load hai aur zero hai par screen par user ne data daala hai
        if final_df['total_add_fees'].sum() == 0.0 and manual_ads_value > 0:
            final_df['total_add_fees'] = manual_ads_value / len(final_df)
    else:
        final_df['total_add_fees'] = manual_ads_value / len(final_df)

    # Core Metrics Calculations
    s_gross = final_df['gross_sale_amt'].sum() if 'gross_sale_amt' in final_df.columns else 0.0
    s_refund = final_df['total_refund'].sum() if 'total_refund' in final_df.columns else 0.0
    s_fees = final_df['marketplace_fees'].sum() if 'marketplace_fees' in final_df.columns else 0.0
    s_ads = final_df['total_add_fees'].sum()
    s_net = final_df['net_settled_amount'].sum() if 'net_settled_amount' in final_df.columns else 0.0

    # Layout Metrics Row
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-title">Gross Sales</div><div class="metric-value">₹ {s_gross:,.2f}</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card"><div class="metric-title">Total Refund</div><div class="metric-value">₹ {s_refund:,.2f}</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-title">Marketplace Fees</div><div class="metric-value">₹ {s_fees:,.2f}</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-title">Total ADD Fees (Ads)</div><div class="metric-value">₹ {s_ads:,.2f}</div></div>', unsafe_allow_html=True)
    with m5: st.markdown(f'<div class="metric-card"><div class="metric-title">Net Settled</div><div class="metric-value">₹ {s_net:,.2f}</div></div>', unsafe_allow_html=True)

    # Graph Section
    st.subheader("📊 Top Designs Performance")
    top_designs = final_df.groupby('design')['net_settled_amount'].sum().reset_index().sort_values(by='net_settled_amount', ascending=False).head(10)
    fig = px.bar(top_designs, x='net_settled_amount', y='design', orientation='h', title="Top 10 SKU", color='net_settled_amount', color_continuous_scale='Bluered')
    st.plotly_chart(fig, use_container_width=True)

    # Breakdown Dataframe Grid
    st.subheader("📋 Design-Wise Data Grid")
    grid_df = final_df.copy()
    for c in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'total_add_fees', 'net_settled_amount']:
        if c in grid_df.columns:
            grid_df[c] = grid_df[c].apply(lambda x: f"₹ {x:,.2f}")
    st.dataframe(grid_df, use_container_width=True)
else:
    st.info("👋 System Ready! Please upload an Excel sheet to populate the dashboard metrics live.")
