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
st.write("Analyze and manage your e-commerce financial performance seamlessly.")

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.header("⚙️ Control Panel")

# 1. Action Selector
action = st.sidebar.radio("Choose Action:", ["View Dashboard", "Upload Data"], index=0)

# 2. Get DB Schema Dynamically to Prevent Key/Column Errors
db_columns = []
try:
    # Fetch 1 row to inspect valid DB column names
    inspect_query = supabase.table("design_wise_summary").select("*").limit(1).execute()
    if inspect_query.data:
        db_columns = list(inspect_query.data[0].keys())
    else:
        # Fallback if table is empty, try a system query or use standard columns
        db_columns = ["id", "brand", "marketplace", "design", "gross_sale_amt", "total_refund", "marketplace_fees", "total_add_fees", "net_settled_amount", "total_sale_pcs", "sale_qty", "logistics_return_pcs", "logistics_return_qty", "customer_return_pcs", "customer_return_qty"]
except Exception as e:
    db_columns = []

# Check if month_year exists in database schema
has_month_year = "month_year" in db_columns

# Global Filters
available_brands, available_marketplaces, available_months = [], [], []
try:
    select_fields = "brand, marketplace"
    if has_month_year:
        select_fields += ", month_year"
        
    meta_query = supabase.table("design_wise_summary").select(select_fields).execute()
    if meta_query.data:
        meta_df = pd.DataFrame(meta_query.data)
        available_brands = sorted(meta_df['brand'].unique()) if 'brand' in meta_df.columns else []
        available_marketplaces = sorted(meta_df['marketplace'].unique()) if 'marketplace' in meta_df.columns else []
        available_months = sorted(meta_df['month_year'].unique()) if 'month_year' in meta_df.columns else []
except Exception as e:
    pass

selected_brand = st.sidebar.selectbox("Filter Brand:", ["ALL"] + available_brands, index=0)
selected_mp = st.sidebar.selectbox("Filter Marketplace:", ["ALL"] + available_marketplaces, index=0)

# Render Month filter only if DB has this column
if has_month_year:
    selected_month = st.sidebar.selectbox("Filter Month-Year:", ["ALL"] + available_months, index=0)
else:
    selected_month = "ALL"

# --- HELPER: UNIFY COLUMN NAMES ---
def find_and_map_column(df, possible_names, default=None):
    """Finds a column in df matching any of the possible names (case-insensitive)."""
    df_cols_lower = {col.lower().strip(): col for col in df.columns}
    for name in possible_names:
        name_lower = name.lower().strip()
        if name_lower in df_cols_lower:
            return df_cols_lower[name_lower]
    return default

# ==========================================
# ACTION: UPLOAD DATA
# ==========================================
if action == "Upload Data":
    st.header("📤 Upload & Process Financial Report")
    
    upload_brand = st.text_input("Enter Brand Name:", "RECOAPPPY").strip().upper()
    upload_mp = st.selectbox("Select Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])
    
    upload_month = ""
    if has_month_year:
        upload_month = st.text_input("Enter Month-Year (e.g., APR_26):", "APR_26").strip().upper()
    else:
        st.warning("⚠️ Database 'month_year' column nahi mila. Monthly filters disable rahenge jab tak aap database update nahi karte (Option 1).")
    
    uploaded_file = st.file_uploader("Upload Excel/CSV File", type=["xlsx", "csv"])
    
    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            
            # Auto-detect file headers & skip empty rows
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(io.BytesIO(file_bytes))
                if df_raw.columns.str.contains('Unnamed').sum() > len(df_raw.columns) / 2:
                    df_raw = pd.read_csv(io.BytesIO(file_bytes), skiprows=1)
            else:
                df_raw = pd.read_excel(io.BytesIO(file_bytes))
                if df_raw.columns.str.contains('Unnamed').sum() > len(df_raw.columns) / 2:
                    df_raw = pd.read_excel(io.BytesIO(file_bytes), skiprows=1)
            
            st.info("Raw File Loaded successfully!")
            
            # --- Auto-detect Design/SKU Column ---
            detected_design_col = find_and_map_column(df_raw, [
                "fsn", "sku", "design", "style", "style code", "style_code", "product_id", 
                "seller sku", "seller_sku", "sku id", "sku_id", "style no", "style_no", 
                "product id", "channel sku", "channel_sku", "seller sku code", "item code", "item_code"
            ])
            
            # Interactive dropdown fallback
            if not detected_design_col:
                st.warning("⚠️ Column auto-detection fails.")
                design_col = st.selectbox(
                    "👉 Select SKU / Design / Style Code Column:",
                    options=list(df_raw.columns)
                )
            else:
                design_col = detected_design_col
                st.success(f"✅ Automatically mapped SKU/Design to: **'{design_col}'**")

            # Column mappings for metrics
            gross_sale_col = find_and_map_column(df_raw, ["gross sale amt", "sale_amount", "sales", "order amount", "gross sales"])
            refund_col = find_and_map_column(df_raw, ["total refund", "refund", "refund_amount", "customer return value"])
            mp_fees_col = find_and_map_column(df_raw, ["marketplace fees", "fees", "commission", "marketplace_fee"])
            add_fees_col = find_and_map_column(df_raw, ["total add fees", "add_fees", "other_fees", "ads_fees", "advertisement"])
            net_settled_col = find_and_map_column(df_raw, ["net settled amount", "net settled", "payout", "net_amount"])
            
            qty_col = find_and_map_column(df_raw, ["quantity", "qty", "pieces", "pcs", "ordered qty", "sale qty", "sale_qty", "total_sale_pcs"])
            return_type_col = find_and_map_column(df_raw, ["return type", "return_type", "order status", "status", "shipment status"])
            logistics_col = find_and_map_column(df_raw, ["logistics return", "logistics_return_pcs", "rto qty", "rto_quantity"])
            customer_ret_col = find_and_map_column(df_raw, ["customer return", "customer_return_pcs", "customer return qty"])

            if st.button("Process & Upload Data"):
                df_raw[design_col] = df_raw[design_col].astype(str).str.strip()
                
                # Quantity calculation
                if qty_col:
                    df_raw['Clean_Qty'] = pd.to_numeric(df_raw[qty_col], errors='coerce').fillna(0).astype(int)
                else:
                    df_raw['Clean_Qty'] = 1  
                
                # Check for returns
                if return_type_col:
                    df_raw['Temp_Return'] = df_raw[return_type_col].astype(str).str.strip().fillna('NA')
                    df_raw['Is_Sale'] = np.where(df_raw['Temp_Return'].str.contains('rto|customer|return|cancelled', case=False, na=False), 0, df_raw['Clean_Qty'])
                    df_raw['Logistics_Return'] = np.where(df_raw['Temp_Return'].str.contains('rto|dto|courier', case=False, na=False), df_raw['Clean_Qty'], 0)
                    df_raw['Customer_Return'] = np.where(df_raw['Temp_Return'].str.contains('customer', case=False, na=False), df_raw['Clean_Qty'], 0)
                else:
                    df_raw['Logistics_Return'] = pd.to_numeric(df_raw[logistics_col], errors='coerce').fillna(0).astype(int) if logistics_col else 0
                    df_raw['Customer_Return'] = pd.to_numeric(df_raw[customer_ret_col], errors='coerce').fillna(0).astype(int) if customer_ret_col else 0
                    df_raw['Is_Sale'] = df_raw['Clean_Qty'] - df_raw['Logistics_Return'] - df_raw['Customer_Return']
                    df_raw['Is_Sale'] = df_raw['Is_Sale'].clip(lower=0)

                # Map numeric fields
                def clean_numeric(col_name):
                    if col_name:
                        return pd.to_numeric(df_raw[col_name], errors='coerce').fillna(0)
                    return pd.Series(0, index=df_raw.index)

                df_raw['Gross_Sale_Clean'] = clean_numeric(gross_sale_col)
                df_raw['Refund_Clean'] = clean_numeric(refund_col)
                df_raw['Fees_Clean'] = clean_numeric(mp_fees_col)
                df_raw['Add_Fees_Clean'] = clean_numeric(add_fees_col)
                df_raw['Net_Settled_Clean'] = clean_numeric(net_settled_col)

                # Group by Design / SKU
                summary_df = df_raw.groupby(design_col).agg({
                    'Gross_Sale_Clean': 'sum',
                    'Refund_Clean': 'sum',
                    'Fees_Clean': 'sum',
                    'Add_Fees_Clean': 'sum',
                    'Net_Settled_Clean': 'sum',
                    'Is_Sale': 'sum',
                    'Logistics_Return': 'sum',
                    'Customer_Return': 'sum'
                }).reset_index()

                # Build Payload dynamic safe-check
                db_payload = []
                for _, row in summary_df.iterrows():
                    item = {
                        "brand": upload_brand,
                        "marketplace": upload_mp,
                        "design": str(row[design_col]),
                        "gross_sale_amt": float(row['Gross_Sale_Clean']),
                        "total_refund": float(row['Refund_Clean']),
                        "marketplace_fees": float(row['Fees_Clean']),
                        "total_add_fees": float(row['Add_Fees_Clean']),
                        "net_settled_amount": float(row['Net_Settled_Clean']),
                        "total_sale_pcs": int(row['Is_Sale']),
                        "sale_qty": int(row['Is_Sale']),
                        "logistics_return_pcs": int(row['Logistics_Return']),
                        "logistics_return_qty": int(row['Logistics_Return']),
                        "customer_return_pcs": int(row['Customer_Return']),
                        "customer_return_qty": int(row['Customer_Return'])
                    }
                    # Insert 'month_year' ONLY if column exists in Supabase DB schema
                    if has_month_year:
                        item["month_year"] = upload_month
                        
                    db_payload.append(item)

                if db_payload:
                    # Clear old records
                    delete_query = supabase.table("design_wise_summary").delete()\
                        .eq("marketplace", upload_mp)\
                        .eq("brand", upload_brand)
                        
                    if has_month_year:
                        delete_query = delete_query.eq("month_year", upload_month)
                        
                    delete_query.execute()
                    
                    # Insert batch
                    supabase.table("design_wise_summary").insert(db_payload).execute()
                    st.success(f"Processed and uploaded {len(db_payload)} records successfully!")
                    st.dataframe(pd.DataFrame(db_payload).head(10))
                else:
                    st.warning("No rows found to process.")
                    
        except Exception as e:
            st.error(f"Error processing sheet: {str(e)}")

# ==========================================
# ACTION: VIEW DASHBOARD
# ==========================================
else:
    try:
        query = supabase.table("design_wise_summary").select("*")
        if selected_brand != "ALL":
            query = query.eq("brand", selected_brand)
        if selected_mp != "ALL":
            query = query.eq("marketplace", selected_mp)
        if has_month_year and selected_month != "ALL":
            query = query.eq("month_year", selected_month)
            
        response = query.execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            
            # Map dynamic DB fields
            def align_column(df, target_col, candidate_names):
                matched = find_and_map_column(df, candidate_names)
                if matched:
                    df[target_col] = pd.to_numeric(df[matched], errors='coerce').fillna(0)
                else:
                    df[target_col] = 0.0

            align_column(df, 'gross_sale_amt', ['gross_sale_amt', 'gross_sales'])
            align_column(df, 'total_refund', ['total_refund', 'refund'])
            align_column(df, 'marketplace_fees', ['marketplace_fees', 'fees'])
            align_column(df, 'total_add_fees', ['total_add_fees', 'add_fees'])
            align_column(df, 'net_settled_amount', ['net_settled_amount', 'net_settled'])
            
            align_column(df, 'total_sale_pcs', ['total_sale_pcs', 'sale_qty', 'is_sale'])
            align_column(df, 'logistics_return_pcs', ['logistics_return_pcs', 'logistics_return_qty'])
            align_column(df, 'customer_return_pcs', ['customer_return_pcs', 'customer_return_qty'])

            # --- CALCULATE METRICS ---
            total_sales_val = df['gross_sale_amt'].sum()
            total_refund_val = df['total_refund'].sum()
            total_fees_val = df['marketplace_fees'].sum()
            total_add_val = df['total_add_fees'].sum()
            total_net_val = df['net_settled_amount'].sum()
            
            total_sale_qty = int(df['total_sale_pcs'].sum())
            total_log_qty = int(df['logistics_return_pcs'].sum())
            total_cust_qty = int(df['customer_return_pcs'].sum())
            total_dispatch_qty = total_sale_qty + total_log_qty + total_cust_qty
            
            # KPIs cards
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Gross Sales</div><div class="metric-value">₹ {total_sales_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Total Refund</div><div class="metric-value">₹ {total_refund_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Marketplace Fees</div><div class="metric-value">₹ {total_fees_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col4:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Total ADD Fees</div><div class="metric-value">₹ {total_add_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col5:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Net Settled</div><div class="metric-value">₹ {total_net_val:,.2f}</div></div>', unsafe_allow_html=True)

            # Quantities Section
            st.subheader("📦 Order & Returns Volume")
            q1, q2, q3, q4 = st.columns(4)
            with q1:
                st.metric("Total Dispatches (Calculated)", f"{total_dispatch_qty} pcs")
            with q2:
                st.metric("Total Sales Pcs", f"{total_sale_qty} pcs")
            with q3:
                st.metric("Logistics Return Pcs", f"{total_log_qty} pcs")
            with q4:
                st.metric("Customer Return Pcs", f"{total_cust_qty} pcs")

            # --- VISUALIZATION ---
            st.subheader("📊 Top Designs Performance")
            top_designs = df.groupby('design')['net_settled_amount'].sum().reset_index().sort_values(by='net_settled_amount', ascending=False).head(10)
            fig = px.bar(
                top_designs, 
                x='net_settled_amount', 
                y='design', 
                orientation='h', 
                title="Top 10 Designs by Net Settled Value",
                labels={'net_settled_amount': 'Net Settled (₹)', 'design': 'Design/SKU'},
                color='net_settled_amount',
                color_continuous_scale='Bluered'
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

            # --- DETAILED DATA TABLE ---
            st.subheader("📋 Design-Wise Detailed Breakdown")
            display_df = df.groupby('design').agg({
                'total_sale_pcs': 'sum',
                'logistics_return_pcs': 'sum',
                'customer_return_pcs': 'sum',
                'gross_sale_amt': 'sum',
                'total_refund': 'sum',
                'marketplace_fees': 'sum',
                'total_add_fees': 'sum',
                'net_settled_amount': 'sum'
            }).reset_index()
            
            formatted_df = display_df.copy()
            for col in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'total_add_fees', 'net_settled_amount']:
                formatted_df[col] = formatted_df[col].apply(lambda x: f"₹ {x:,.2f}")
            
            st.dataframe(formatted_df, use_container_width=True, height=400)
        else:
            st.info("No records found in database. Please upload some data using 'Upload Data' tab in sidebar!")
    except Exception as e:
        st.error(f"Error: {str(e)}")
