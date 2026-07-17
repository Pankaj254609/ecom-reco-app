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

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.header("⚙️ Control Panel")
action = st.sidebar.radio("Choose Action:", ["View Dashboard", "Upload Data"], index=0)

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
except Exception:
    pass

selected_brand = st.sidebar.selectbox("Filter Brand:", ["ALL"] + available_brands, index=0)
selected_mp = st.sidebar.selectbox("Filter Marketplace:", ["ALL"] + available_marketplaces, index=0)
selected_month = st.sidebar.selectbox("Filter Month:", ["ALL"] + available_months, index=0) if (has_month_year or has_month) else "ALL"

# Helper for robust case-insensitive default index lookup
def get_default_idx(lst, keywords):
    for kw in keywords:
        for idx, col in enumerate(lst):
            if kw.lower() in str(col).lower():
                return idx
    return 0

# ==========================================
# ACTION: UPLOAD DATA
# ==========================================
if action == "Upload Data":
    st.header("📤 Upload & Process Financial Report")
    
    upload_brand = st.text_input("Enter Brand Name:", "VIDA LOCA").strip().upper()
    upload_mp = st.selectbox("Select Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])
    
    uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])
    
    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            xls_file = pd.ExcelFile(io.BytesIO(file_bytes))
            
            # --- 1. PROCESS ORDERS SHEET ---
            orders_sheet = 'Orders' if 'Orders' in xls_file.sheet_names else xls_file.sheet_names[0]
            df_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=orders_sheet)
            
            # Smart Header Resolver for Orders Sheet
            target_keywords = ['sku', 'seller sku', 'sale amount', 'my share', 'refund']
            for i in range(min(15, df_raw.shape[0])):
                row_str_vals = [str(x).lower().strip() for x in df_raw.iloc[i].values]
                if any(k in row_str_vals for k in target_keywords):
                    df_raw.columns = df_raw.iloc[i]
                    df_raw = df_raw[i+1:].reset_index(drop=True)
                    break
            
            df_raw.columns = [str(c).strip() for c in df_raw.columns]
            all_file_cols = list(df_raw.columns)
            
            st.warning("🎯 **Please match the Columns for 'Orders' Sheet:**")
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                design_col = st.selectbox("Select SKU / Design Column (Orders):", all_file_cols, index=get_default_idx(all_file_cols, ["seller sku", "sku", "design"]))
                gross_sale_col = st.selectbox("Select Gross Sales Column:", all_file_cols, index=get_default_idx(all_file_cols, ["sale amount total", "gross sales", "sale amount"]))
                refund_col = st.selectbox("Select Total Refund Column:", all_file_cols, index=get_default_idx(all_file_cols, ["refund"]))
            
            with col_sel2:
                mp_fees_col = st.selectbox("Select Marketplace Fees Column:", all_file_cols, index=get_default_idx(all_file_cols, ["marketplace fee", "fees", "fee"]))
                net_settled_col = st.selectbox("Select Net Settled Column:", all_file_cols, index=get_default_idx(all_file_cols, ["my share", "net settled", "settlement"]))
                qty_col = st.selectbox("Select Quantity Column:", all_file_cols, index=get_default_idx(all_file_cols, ["quantity", "qty"]))
                
            return_status_col = st.selectbox("Select Return Type Column (Optional):", ["None"] + all_file_cols, index=get_default_idx(["None"] + all_file_cols, ["return type", "status"]))

            # --- 2. PROCESS ADS SHEET ---
            df_ads_summary = pd.DataFrame(columns=['design', 'Ads_Cost'])
            ads_sheet_name = next((s for s in xls_file.sheet_names if 'ad' in s.lower()), None)
            
            if ads_sheet_name:
                df_ads_raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=ads_sheet_name)
                
                # Smart Header Resolver for Ads Sheet
                for i in range(min(10, df_ads_raw.shape[0])):
                    row_vals_ads = [str(x).lower().strip() for x in df_ads_raw.iloc[i].values]
                    if 'settlement' in row_vals_ads or 'sku' in row_vals_ads or 'ad' in row_vals_ads:
                        df_ads_raw.columns = df_ads_raw.iloc[i]
                        df_ads_raw = df_ads_raw[i+1:].reset_index(drop=True)
                        break
                
                df_ads_raw.columns = [str(c).strip() for c in df_ads_raw.columns]
                all_ads_cols = list(df_ads_raw.columns)
                
                st.info(f"📈 **Please match the Columns for Ads Sheet ('{ads_sheet_name}'):**")
                col_ads1, col_ads2 = st.columns(2)
                with col_ads1:
                    ads_sku_col = st.selectbox("Select SKU Column (Ads Sheet):", all_ads_cols, index=get_default_idx(all_ads_cols, ["seller sku", "sku", "design"]))
                with col_ads2:
                    ads_val_col = st.selectbox("Select Ads Cost / Settlement Value Column:", all_ads_cols, index=get_default_idx(all_ads_cols, ["settlement value", "ad cost", "cost", "amount"]))
                
                # Pre-process Ads mapping values safely
                if ads_sku_col and ads_val_col:
                    df_ads_raw[ads_sku_col] = df_ads_raw[ads_sku_col].astype(str).str.strip()
                    s_ads = df_ads_raw[ads_val_col].astype(str).str.replace('₹', '').str.replace(',', '').str.replace(' ', '').str.strip()
                    df_ads_raw['Ads_Cost_Clean'] = pd.to_numeric(s_ads, errors='coerce').fillna(0)
                    
                    df_ads_summary = df_ads_raw.groupby(ads_sku_col)['Ads_Cost_Clean'].sum().reset_index()
                    df_ads_summary.columns = ['design', 'Ads_Cost']
                    st.success(f"✅ Ads Data mapped completely from sheet '{ads_sheet_name}'")
            else:
                st.warning("⚠️ No 'Ads' sheet detected in the file. Total Add Fees will be processed as 0.00")

            # Date / Month Selector
            date_col = next((c for c in all_file_cols if 'date' in c.lower() or 'time' in c.lower()), None)
            detected_month_val = "UNKNOWN"
            if date_col:
                try:
                    first_val = df_raw[date_col].dropna().iloc[0]
                    parsed_d = pd.to_datetime(first_val, errors='coerce')
                    if not pd.isnull(parsed_d):
                        detected_month_val = parsed_d.strftime('%b_%y').upper()
                except Exception:
                    pass
            
            upload_month = st.text_input("Confirm Month Value:", value=detected_month_val).strip().upper()

            if st.button("🚀 Process & Upload Data Now"):
                df_raw[design_col] = df_raw[design_col].astype(str).str.strip()
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
                    s = df_raw[col_n].astype(str).str.replace('₹', '').str.replace(',', '').str.replace(' ', '').str.strip()
                    return pd.to_numeric(s, errors='coerce').fillna(0)

                df_raw['Gross_Sale_Clean'] = clean_numeric_series(gross_sale_col)
                df_raw['Refund_Clean'] = clean_numeric_series(refund_col)
                df_raw['Fees_Clean'] = clean_numeric_series(mp_fees_col)
                df_raw['Net_Settled_Clean'] = clean_numeric_series(net_settled_col)

                # Group values safely
                summary_df = df_raw.groupby(design_col).agg({
                    'Gross_Sale_Clean': 'sum',
                    'Refund_Clean': 'sum',
                    'Fees_Clean': 'sum',
                    'Net_Settled_Clean': 'sum',
                    'Is_Sale': 'sum',
                    'Logistics_Return': 'sum',
                    'Customer_Return': 'sum'
                }).reset_index()
                
                summary_df.columns = ['design', 'Gross_Sale', 'Refund', 'Fees', 'Net_Settled', 'Sales_Pcs', 'Log_Pcs', 'Cust_Pcs']

                # Merge processed ads summary
                if not df_ads_summary.empty:
                    summary_df = pd.merge(summary_df, df_ads_summary, on='design', how='left').fillna(0)
                else:
                    summary_df['Ads_Cost'] = 0.0

                db_payload = []
                for _, row in summary_df.iterrows():
                    all_fields = {
                        "brand": upload_brand,
                        "marketplace": upload_mp,
                        "design": str(row['design']),
                        "gross_sale_amt": float(row['Gross_Sale']),
                        "total_refund": float(row['Refund']),
                        "marketplace_fees": float(row['Fees']),
                        "total_add_fees": float(row['Ads_Cost']),
                        "net_settled_amount": float(row['Net_Settled']),
                        "total_sale_pcs": int(row['Sales_Pcs']),
                        "sale_qty": int(row['Sales_Pcs']),
                        "logistics_return_pcs": int(row['Log_Pcs']),
                        "logistics_return_qty": int(row['Log_Pcs']),
                        "customer_return_pcs": int(row['Cust_Pcs']),
                        "customer_return_qty": int(row['Cust_Pcs']),
                        "month": upload_month,
                        "month_year": upload_month
                    }
                    safe_item = {k: v for k, v in all_fields.items() if k in db_columns}
                    db_payload.append(safe_item)

                if db_payload:
                    try:
                        del_q = supabase.table("design_wise_summary").delete().eq("marketplace", upload_mp).eq("brand", upload_brand)
                        if has_month:
                            del_q = del_q.eq("month", upload_month)
                        elif has_month_year:
                            del_q = del_q.eq("month_year", upload_month)
                        del_q.execute()
                    except Exception:
                        pass
                    
                    supabase.table("design_wise_summary").insert(db_payload).execute()
                    st.success(f"🎉 Success! Uploaded {len(db_payload)} row metrics database records with Ads Data!")
                    st.balloons()
                else:
                    st.error("No valid calculations produced. Check layout values format.")
        except Exception as e:
            st.error(f"Error parsing sheet columns: {str(e)}")

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
            
            df['gross_sale_amt'] = pd.to_numeric(df.get('gross_sale_amt', 0), errors='coerce').fillna(0)
            df['total_refund'] = pd.to_numeric(df.get('total_refund', 0), errors='coerce').fillna(0)
            df['marketplace_fees'] = pd.to_numeric(df.get('marketplace_fees', 0), errors='coerce').fillna(0)
            df['total_add_fees'] = pd.to_numeric(df.get('total_add_fees', 0), errors='coerce').fillna(0)
            df['net_settled_amount'] = pd.to_numeric(df.get('net_settled_amount', 0), errors='coerce').fillna(0)
            
            df['total_sale_pcs'] = pd.to_numeric(df.get('total_sale_pcs', df.get('sale_qty', 0)), errors='coerce').fillna(0)
            df['logistics_return_pcs'] = pd.to_numeric(df.get('logistics_return_pcs', df.get('logistics_return_qty', 0)), errors='coerce').fillna(0)
            df['customer_return_pcs'] = pd.to_numeric(df.get('customer_return_pcs', df.get('customer_return_qty', 0)), errors='coerce').fillna(0)

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
                st.markdown(f'<div class="metric-card"><div class="metric-title">Total ADD Fees (Ads)</div><div class="metric-value">₹ {total_add_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col5:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Net Settled</div><div class="metric-value">₹ {total_net_val:,.2f}</div></div>', unsafe_allow_html=True)

            st.subheader("📦 Order & Returns Volume")
            q1, q2, q3, q4 = st.columns(4)
            with q1:
                st.metric("Total Dispatches", f"{total_dispatch_qty} pcs")
            with q2:
                st.metric("Total Sales Pcs (Delivered)", f"{total_sale_qty} pcs")
            with q3:
                st.metric("Logistics Return Pcs", f"{total_log_qty} pcs")
            with q4:
                st.metric("Customer Return Pcs", f"{total_cust_qty} pcs")

            st.subheader("📊 Top Designs Performance")
            top_designs = df.groupby('design')['net_settled_amount'].sum().reset_index().sort_values(by='net_settled_amount', ascending=False).head(10)
            fig = px.bar(top_designs, x='net_settled_amount', y='design', orientation='h', title="Top 10 Designs by Net Settled Value", labels={'net_settled_amount': 'Net Settled (₹)', 'design': 'Design/SKU'}, color='net_settled_amount', color_continuous_scale='Bluered')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📋 Design-Wise Detailed Breakdown")
            display_df = df.groupby('design').agg({'total_sale_pcs': 'sum', 'logistics_return_pcs': 'sum', 'customer_return_pcs': 'sum', 'gross_sale_amt': 'sum', 'total_refund': 'sum', 'marketplace_fees': 'sum', 'total_add_fees': 'sum', 'net_settled_amount': 'sum'}).reset_index()
            formatted_df = display_df.copy()
            for col in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'total_add_fees', 'net_settled_amount']:
                formatted_df[col] = formatted_df[col].apply(lambda x: f"₹ {x:,.2f}")
            st.dataframe(formatted_df, use_container_width=True, height=400)
        else:
            st.info("No records found. Please upload your Excel sheet via the 'Upload Data' tab first!")
    except Exception as e:
        st.error(f"Error rendering metrics dashboard: {str(e)}")
