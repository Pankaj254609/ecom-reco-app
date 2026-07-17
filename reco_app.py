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

action = st.sidebar.radio("Choose Action:", ["View Dashboard", "Upload Data"], index=0)

# Fetch Dynamic Database Columns
db_columns = []
try:
    inspect_query = supabase.table("design_wise_summary").select("*").limit(1).execute()
    if inspect_query.data:
        db_columns = [col.lower().strip() for col in inspect_query.data[0].keys()]
    else:
        db_columns = ["brand", "marketplace", "design", "gross_sale_amt", "total_refund", "marketplace_fees", "total_add_fees", "net_settled_amount", "total_sale_pcs", "sale_qty", "logistics_return_pcs", "logistics_return_qty", "customer_return_pcs", "customer_return_qty", "month", "month_year"]
except Exception as e:
    db_columns = ["brand", "marketplace", "design", "gross_sale_amt", "total_refund", "marketplace_fees", "total_add_fees", "net_settled_amount", "total_sale_pcs", "sale_qty", "logistics_return_pcs", "logistics_return_qty", "customer_return_pcs", "customer_return_qty", "month", "month_year"]

has_month_year = "month_year" in db_columns
has_month = "month" in db_columns

# Global Filters Data Load
available_brands, available_marketplaces, available_months = [], [], []
try:
    select_fields = "brand, marketplace"
    if has_month_year:
        select_fields += ", month_year"
    elif has_month:
        select_fields += ", month"
        
    meta_query = supabase.table("design_wise_summary").select(select_fields).execute()
    if meta_query.data:
        meta_df = pd.DataFrame(meta_query.data)
        available_brands = sorted(meta_df['brand'].unique()) if 'brand' in meta_df.columns else []
        available_marketplaces = sorted(meta_df['marketplace'].unique()) if 'marketplace' in meta_df.columns else []
        
        if 'month_year' in meta_df.columns:
            available_months = sorted(meta_df['month_year'].unique())
        elif 'month' in meta_df.columns:
            available_months = sorted(meta_df['month'].unique())
except Exception as e:
    pass

selected_brand = st.sidebar.selectbox("Filter Brand:", ["ALL"] + available_brands, index=0)
selected_mp = st.sidebar.selectbox("Filter Marketplace:", ["ALL"] + available_marketplaces, index=0)
selected_month = st.sidebar.selectbox("Filter Month:", ["ALL"] + available_months, index=0) if (has_month_year or has_month) else "ALL"

# Helper for strict matching or fallback case-insensitive lookup
def find_and_map_column(df, possible_names, default=None):
    df_cols_lower = {str(col).lower().strip(): col for col in df.columns}
    for name in possible_names:
        name_lower = str(name).lower().strip()
        if name_lower in df_cols_lower:
            return df_cols_lower[name_lower]
    return default

# ==========================================
# ACTION: UPLOAD DATA
# ==========================================
if action == "Upload Data":
    st.header("📤 Upload & Process Financial Report")
    
    upload_brand = st.text_input("Enter Brand Name:", "VIDA LOCA").strip().upper()
    upload_mp = st.selectbox("Select Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])
    
    uploaded_file = st.file_uploader("Upload Excel/CSV File", type=["xlsx", "csv"])
    
    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(io.BytesIO(file_bytes))
            else:
                xls_file = pd.ExcelFile(io.BytesIO(file_bytes))
                target_sheet = 'Orders' if 'Orders' in xls_file.sheet_names else xls_file.sheet_names[0]
                df_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=target_sheet)
                
                # Sheet adjustments header detection row bypass
                if 'Seller SKU' not in df_raw.columns and df_raw.shape[0] > 1:
                    for i in range(min(5, df_raw.shape[0])):
                        if 'Seller SKU' in df_raw.iloc[i].values:
                            df_raw.columns = df_raw.iloc[i]
                            df_raw = df_raw[i+1:].reset_index(drop=True)
                            break
            
            st.info(f"Loaded rows: {df_raw.shape[0]} | Columns detected: {list(df_raw.columns)[:5]}...")
            
            # --- EXACT FLIPKART REPORT HEADERS MAPPING ---
            design_col = find_and_map_column(df_raw, ["Seller SKU"])
            date_col = find_and_map_column(df_raw, ["Payment date"])
            gross_sale_col = find_and_map_column(df_raw, ["Sale Amount Total (Rs.)"])
            refund_col = find_and_map_column(df_raw, ["Refund (Rs.)"])
            mp_fees_col = find_and_map_column(df_raw, ["Marketplace Fee (Rs.)"])
            add_fees_col = find_and_map_column(df_raw, ["Protection Fund (Rs.)"])
            net_settled_col = find_and_map_column(df_raw, ["My share (Rs.)"])
            qty_col = find_and_map_column(df_raw, ["Quantity"])
            return_status_col = find_and_map_column(df_raw, ["Return Type"])

            # Fallbacks just in case case matches slightly differ
            if not design_col: design_col = find_and_map_column(df_raw, ["seller sku", "sku", "design"])
            if not qty_col: qty_col = find_and_map_column(df_raw, ["quantity", "qty"])
            if not return_status_col: return_status_col = find_and_map_column(df_raw, ["return type", "status"])

            if not design_col:
                st.error("❌ 'Seller SKU' column not found in report headers! Please verify your sheet headers format.")
                st.stop()

            # --- DYNAMIC MONTH DETECTION FROM PAYMENT DATE ---
            detected_month_val = "UNKNOWN"
            if date_col:
                try:
                    first_valid_date = df_raw[date_col].dropna().iloc[0]
                    parsed_date = pd.to_datetime(first_valid_date, errors='coerce')
                    if not pd.isnull(parsed_date):
                        detected_month_val = parsed_date.strftime('%b_%y').upper()
                        st.success(f"📅 Automatically matched Month from '{date_col}': **{detected_month_val}**")
                except Exception:
                    pass
            
            upload_month = st.text_input("Confirm/Edit Month Value:", value=detected_month_val).strip().upper()

            if st.button("Process & Upload Data"):
                df_raw[design_col] = df_raw[design_col].astype(str).str.strip()
                df_raw['Clean_Qty'] = pd.to_numeric(df_raw[qty_col], errors='coerce').fillna(0).astype(int) if qty_col else 1
                
                # --- FLIPKART EXACT RETURN MAPPING SCHEME ---
                if return_status_col:
                    # Clean strings and treat spaces/nan properly
                    df_raw['Temp_Status'] = df_raw[return_status_col].astype(str).str.strip().str.lower().fillna('na')
                    df_raw['Temp_Status'] = df_raw['Temp_Status'].replace(['nan', '', 'none'], 'na')

                    # 1. Logistics Return conditions
                    df_raw['Logistics_Return'] = np.where(df_raw['Temp_Status'].str.contains('logistics return|rto|courier', na=False), df_raw['Clean_Qty'], 0)
                    
                    # 2. Customer Return conditions
                    df_raw['Customer_Return'] = np.where(df_raw['Temp_Status'].str.contains('customer return|returned|refunded', na=False), df_raw['Clean_Qty'], 0)
                    
                    # 3. Delivered/Sale conditions (If NA, or empty, or contains 'delivered')
                    df_raw['Is_Sale'] = np.where(
                        df_raw['Temp_Status'].str.contains('na|delivered', na=False) & (df_raw['Logistics_Return'] == 0) & (df_raw['Customer_Return'] == 0),
                        df_raw['Clean_Qty'],
                        0
                    )
                else:
                    df_raw['Is_Sale'] = df_raw['Clean_Qty']
                    df_raw['Logistics_Return'] = 0
                    df_raw['Customer_Return'] = 0

                def clean_numeric(col_name):
                    return pd.to_numeric(df_raw[col_name], errors='coerce').fillna(0) if col_name else pd.Series(0.0, index=df_raw.index)

                df_raw['Gross_Sale_Clean'] = clean_numeric(gross_sale_col)
                df_raw['Refund_Clean'] = clean_numeric(refund_col)
                df_raw['Fees_Clean'] = clean_numeric(mp_fees_col)
                df_raw['Add_Fees_Clean'] = clean_numeric(add_fees_col)
                df_raw['Net_Settled_Clean'] = clean_numeric(net_settled_col)

                # Summary Calculations Grouping
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

                db_payload = []
                for _, row in summary_df.iterrows():
                    all_fields = {
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
                        "customer_return_qty": int(row['Customer_Return']),
                        "month": upload_month,
                        "month_year": upload_month
                    }
                    
                    safe_item = {k: v for k, v in all_fields.items() if k in db_columns}
                    db_payload.append(safe_item)

                if db_payload:
                    # Clear older transactions index
                    try:
                        delete_query = supabase.table("design_wise_summary").delete().eq("marketplace", upload_mp).eq("brand", upload_brand)
                        if has_month:
                            delete_query = delete_query.eq("month", upload_month)
                        elif has_month_year:
                            delete_query = delete_query.eq("month_year", upload_month)
                        delete_query.execute()
                    except Exception:
                        pass
                    
                    # Batch Sync to Database
                    supabase.table("design_wise_summary").insert(db_payload).execute()
                    st.success(f"Processed and uploaded {len(db_payload)} records successfully for month {upload_month}!")
                    st.dataframe(pd.DataFrame(db_payload).head(5))
                else:
                    st.warning("Processed payload outputs returned empty.")
                    
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
        if selected_month != "ALL":
            if has_month:
                query = query.eq("month", selected_month)
            elif has_month_year:
                query = query.eq("month_year", selected_month)
            
        response = query.execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            
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
            
            align_column(df, 'total_sale_pcs', ['total_sale_pcs', 'sale_qty'])
            align_column(df, 'logistics_return_pcs', ['logistics_return_pcs', 'logistics_return_qty'])
            align_column(df, 'customer_return_pcs', ['customer_return_pcs', 'customer_return_qty'])

            # --- RENDER DASHBOARD METRICS ---
            total_sales_val = df['gross_sale_amt'].sum()
            total_refund_val = df['total_refund'].sum()
            total_fees_val = df['marketplace_fees'].sum()
            total_add_val = df['total_add_fees'].sum()
            total_net_val = df['net_settled_amount'].sum()
            
            total_sale_qty = int(df['total_sale_pcs'].sum())
            total_log_qty = int(df['logistics_return_pcs'].sum())
            total_cust_qty = int(df['customer_return_pcs'].sum())
            total_dispatch_qty = total_sale_qty + total_log_qty + total_cust_qty
            
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

            st.subheader("📦 Order & Returns Volume")
            q1, q2, q3, q4 = st.columns(4)
            with q1:
                st.metric("Total Dispatches", f"{total_dispatch_qty} pcs")
            with q2:
                st.metric("Total Sales Pcs", f"{total_sale_qty} pcs")
            with q3:
                st.metric("Logistics Return Pcs", f"{total_log_qty} pcs")
            with q4:
                st.metric("Customer Return Pcs", f"{total_cust_qty} pcs")

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
            st.info("No records found. Please upload data via the 'Upload Data' tab first!")
    except Exception as e:
        st.error(f"Error displaying dashboard: {str(e)}")
