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

# --- STATE MANAGEMENT ---
if 'last_manual_ads_dict' not in st.session_state:
    st.session_state['last_manual_ads_dict'] = {}

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.header("⚙️ Control Panel")
action = st.sidebar.radio("Choose Action:", ["View Dashboard", "Upload Data", "Manage SKU Mapping"], index=0)

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

def get_default_idx(lst, keywords):
    for kw in keywords:
        for idx, col in enumerate(lst):
            if kw.lower() in str(col).lower():
                return idx
    return 0

# ==========================================
# ACTION: MANAGE SKU MAPPING (NEW PERMANENT MAPPING)
# ==========================================
if action == "Manage SKU Mapping":
    st.header("🔗 Manage SKU to Design Mapping")
    st.markdown("Yahan save ki hui mapping automatically 'Upload Data' karte waqt use hogi.")
    
    tab1, tab2, tab3 = st.tabs(["Bulk Upload (Excel)", "Add Single SKU", "View Mappings"])
    
    with tab1:
        st.subheader("Bulk Upload 'CHANEL MAPING SKU' Sheet")
        mapping_file = st.file_uploader("Upload Excel File", type=["xlsx", "csv"], key="map_file")
        if mapping_file and st.button("Save/Update Bulk Mapping"):
            try:
                if mapping_file.name.endswith('.csv'):
                    df_map = pd.read_csv(mapping_file)
                else:
                    df_map = pd.read_excel(mapping_file)
                
                if 'Seller SKU on Channel' in df_map.columns and 'DESIGN' in df_map.columns:
                    mapping_data = []
                    for _, row in df_map.iterrows():
                        sku = str(row['Seller SKU on Channel']).strip().upper()
                        design = str(row['DESIGN']).strip().upper()
                        if sku and sku != 'NAN':
                            mapping_data.append({"seller_sku": sku, "design": design})
                    
                    # Upload in chunks
                    chunk_size = 500
                    for k in range(0, len(mapping_data), chunk_size):
                        supabase.table("sku_mapping").upsert(mapping_data[k : k + chunk_size]).execute()
                        
                    st.success(f"✅ {len(mapping_data)} SKUs successfully mapped in Database!")
                else:
                    st.error("Sheet mein 'Seller SKU on Channel' aur 'DESIGN' columns nahi mile.")
            except Exception as e:
                st.error(f"Error saving to database: {e}. Check if 'sku_mapping' table exists in Supabase.")

    with tab2:
        st.subheader("Add or Update Single SKU manually")
        new_sku = st.text_input("Enter Seller SKU:").strip().upper()
        new_design = st.text_input("Enter Design Name:").strip().upper()
        if st.button("Save Single Mapping"):
            if new_sku and new_design:
                try:
                    supabase.table("sku_mapping").upsert([{"seller_sku": new_sku, "design": new_design}]).execute()
                    st.success(f"✅ SKU '{new_sku}' mapped to Design '{new_design}' successfully!")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Dono fields bharna zaroori hai.")

    with tab3:
        st.subheader("Current Database Mappings")
        if st.button("Refresh Mapping List"):
            try:
                map_res = supabase.table("sku_mapping").select("*").execute()
                if map_res.data:
                    st.dataframe(pd.DataFrame(map_res.data), use_container_width=True)
                else:
                    st.info("No mappings found in database.")
            except Exception as e:
                st.error("Table read nahi ho paya. Please ensure 'sku_mapping' table is created in Supabase.")

# ==========================================
# ACTION: UPLOAD DATA
# ==========================================
elif action == "Upload Data":
    st.header("📤 Upload & Process Financial Report")
    
    upload_brand = st.text_input("Enter Brand Name:", "VIDA LOCA").strip().upper()
    upload_mp = st.selectbox("Select Marketplace:", ["FLIPKART", "AMAZON", "MEESHO", "MYNTRA"])
    manual_ads_input = st.number_input("💵 Enter Total Ads Cost Manually:", min_value=0.0, value=0.0, step=500.0)
    
    uploaded_file = st.file_uploader("Upload Payment Excel File (.xlsx)", type=["xlsx"])
    
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
            
            st.warning("🎯 **Please match the Columns for 'Orders' Sheet:**")
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                design_col = st.selectbox("Select Seller SKU Column (For Mapping):", all_file_cols, index=get_default_idx(all_file_cols, ["seller sku", "sku", "design"]))
                gross_sale_col = st.selectbox("Select Gross Sales Column:", all_file_cols, index=get_default_idx(all_file_cols, ["sale amount total", "gross sales", "sale amount"]))
                refund_col = st.selectbox("Select Total Refund Column:", all_file_cols, index=get_default_idx(all_file_cols, ["refund"]))
            
            with col_sel2:
                mp_fees_col = st.selectbox("Select Marketplace Fees Column:", all_file_cols, index=get_default_idx(all_file_cols, ["marketplace fee", "fees", "fee"]))
                net_settled_col = st.selectbox("Select Net Settled Column:", all_file_cols, index=get_default_idx(all_file_cols, ["my share", "net settled", "settlement"]))
                qty_col = st.selectbox("Select Quantity Column:", all_file_cols, index=get_default_idx(all_file_cols, ["quantity", "qty"]))
                
            return_status_col = st.selectbox("Select Return Type Column (Optional):", ["None"] + all_file_cols, index=get_default_idx(["None"] + all_file_cols, ["return type", "status"]))

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
                state_key = f"{upload_brand}_{upload_mp}_{upload_month}"
                st.session_state['last_manual_ads_dict'][state_key] = float(manual_ads_input)
                
                df_raw[design_col] = df_raw[design_col].astype(str).str.strip().str.upper()
                
                # Fetch Persistent Mapping from Database
                mapping_dict = {}
                try:
                    map_res = supabase.table("sku_mapping").select("*").execute()
                    if map_res.data:
                        mapping_dict = {row['seller_sku']: row['design'] for row in map_res.data}
                except Exception:
                    pass
                
                if mapping_dict:
                    df_raw['Mapped_Design'] = df_raw[design_col].map(mapping_dict).fillna(df_raw[design_col])
                    st.success(f"✅ Extracted Mapping for {len(mapping_dict)} SKUs from Database!")
                else:
                    df_raw['Mapped_Design'] = df_raw[design_col]
                    st.warning("⚠️ Database mein koi mapping nahi mili. Original SKUs use kar rahe hain.")

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

                summary_df = df_raw.groupby('Mapped_Design').agg({
                    'Gross_Sale_Clean': 'sum',
                    'Refund_Clean': 'sum',
                    'Fees_Clean': 'sum',
                    'Net_Settled_Clean': 'sum',
                    'Is_Sale': 'sum',
                    'Logistics_Return': 'sum',
                    'Customer_Return': 'sum'
                }).reset_index()
                
                summary_df.columns = ['design', 'Gross_Sale', 'Refund', 'Fees', 'Net_Settled', 'Sales_Pcs', 'Log_Pcs', 'Cust_Pcs']

                unique_designs_count = len(summary_df)
                if unique_designs_count > 0 and manual_ads_input > 0:
                    summary_df['Ads_Cost'] = manual_ads_input / unique_designs_count
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
                        supabase.table("design_wise_summary").delete().eq("marketplace", upload_mp).eq("brand", upload_brand).eq("month", upload_month).execute()
                    except Exception:
                        pass
                    
                    chunk_size_insert = 500
                    for k in range(0, len(db_payload), chunk_size_insert):
                        supabase.table("design_wise_summary").insert(db_payload[k : k + chunk_size_insert]).execute()
                        
                    st.success(f"🎉 Success! Data Design-wise convert hoke '{upload_brand}' ke liye add ho gaya hai!")
                    st.balloons()
                else:
                    st.error("Processing generated empty data framework.")
        except Exception as e:
            st.error(f"Error parsing sheet columns: {str(e)}")

# ==========================================
# ACTION: VIEW DASHBOARD
# ==========================================
else:
    try:
        available_brands, available_marketplaces, available_months = [], [], []
        meta_query = supabase.table("design_wise_summary").select("brand, marketplace, month, month_year").limit(5000).execute()
        if meta_query.data:
            meta_df = pd.DataFrame(meta_query.data)
            if 'brand' in meta_df.columns:
                available_brands = sorted([str(x).strip().upper() for x in meta_df['brand'].dropna().unique() if str(x).strip() != ''])
            if 'marketplace' in meta_df.columns:
                available_marketplaces = sorted([str(x).strip().upper() for x in meta_df['marketplace'].dropna().unique() if str(x).strip() != ''])
            if 'month_year' in meta_df.columns and not meta_df['month_year'].dropna().empty:
                available_months = sorted([str(x).strip().upper() for x in meta_df['month_year'].dropna().unique() if str(x).strip() != ''])
            elif 'month' in meta_df.columns:
                available_months = sorted([str(x).strip().upper() for x in meta_df['month'].dropna().unique() if str(x).strip() != ''])

        selected_brand = st.sidebar.selectbox("Filter Brand:", ["ALL"] + available_brands, index=0)
        selected_mp = st.sidebar.selectbox("Filter Marketplace:", ["ALL"] + available_marketplaces, index=0)
        selected_month = st.sidebar.selectbox("Filter Month:", ["ALL"] + available_months, index=0)

        all_dashboard_data = []
        start, chunk_size = 0, 1000
        while True:
            query = supabase.table("design_wise_summary").select("*")
            if selected_brand != "ALL": query = query.eq("brand", selected_brand)
            if selected_mp != "ALL": query = query.eq("marketplace", selected_mp)
            if selected_month != "ALL":
                if has_month: query = query.eq("month", selected_month)
                elif has_month_year: query = query.eq("month_year", selected_month)
                
            response = query.range(start, start + chunk_size - 1).execute()
            if not response.data: break
            all_dashboard_data.extend(response.data)
            if len(response.data) < chunk_size: break
            start += chunk_size
        
        if all_dashboard_data:
            df = pd.DataFrame(all_dashboard_data)
            
            for col in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'net_settled_amount']:
                df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)
            
            df['total_sale_pcs'] = pd.to_numeric(df.get('total_sale_pcs', df.get('sale_qty', 0)), errors='coerce').fillna(0)
            df['logistics_return_pcs'] = pd.to_numeric(df.get('logistics_return_pcs', df.get('logistics_return_qty', 0)), errors='coerce').fillna(0)
            df['customer_return_pcs'] = pd.to_numeric(df.get('customer_return_pcs', df.get('customer_return_qty', 0)), errors='coerce').fillna(0)

            total_sales_val = df['gross_sale_amt'].sum()
            total_refund_val = df['total_refund'].sum()
            total_fees_val = df['marketplace_fees'].sum()
            total_net_val = df['net_settled_amount'].sum()
            
            db_ads_sum = pd.to_numeric(df.get('total_add_fees', 0), errors='coerce').fillna(0).sum()
            if db_ads_sum == 0.0:
                total_add_val = sum(st.session_state['last_manual_ads_dict'].values())
            else:
                total_add_val = db_ads_sum
            
            total_sale_qty = int(df['total_sale_pcs'].sum())
            total_log_qty = int(df['logistics_return_pcs'].sum())
            total_cust_qty = int(df['customer_return_pcs'].sum())
            total_dispatch_qty = total_sale_qty + total_log_qty + total_cust_qty
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.markdown(f'<div class="metric-card"><div class="metric-title">Gross Sales</div><div class="metric-value">₹ {total_sales_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col2: st.markdown(f'<div class="metric-card"><div class="metric-title">Total Refund</div><div class="metric-value">₹ {total_refund_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col3: st.markdown(f'<div class="metric-card"><div class="metric-title">Marketplace Fees</div><div class="metric-value">₹ {total_fees_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col4: st.markdown(f'<div class="metric-card"><div class="metric-title">Total ADD Fees (Ads)</div><div class="metric-value">₹ {total_add_val:,.2f}</div></div>', unsafe_allow_html=True)
            with col5: st.markdown(f'<div class="metric-card"><div class="metric-title">Net Settled</div><div class="metric-value">₹ {total_net_val:,.2f}</div></div>', unsafe_allow_html=True)

            st.subheader("📦 Order & Returns Volume")
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Total Dispatches", f"{total_dispatch_qty} pcs")
            q2.metric("Total Sales Pcs (Delivered)", f"{total_sale_qty} pcs")
            q3.metric("Logistics Return Pcs", f"{total_log_qty} pcs")
            q4.metric("Customer Return Pcs", f"{total_cust_qty} pcs")

            st.subheader("📊 Top Designs Performance")
            top_designs = df.groupby('design')['net_settled_amount'].sum().reset_index().sort_values(by='net_settled_amount', ascending=False).head(10)
            fig = px.bar(top_designs, x='net_settled_amount', y='design', orientation='h', title="Top 10 Designs by Net Settled Value", labels={'net_settled_amount': 'Net Settled (₹)', 'design': 'Design/SKU'}, color='net_settled_amount', color_continuous_scale='Bluered')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📋 Design-Wise Detailed Breakdown")
            display_df = df.groupby(['brand', 'marketplace', 'design']).agg({
                'total_sale_pcs': 'sum', 'logistics_return_pcs': 'sum', 'customer_return_pcs': 'sum', 
                'gross_sale_amt': 'sum', 'total_refund': 'sum', 'marketplace_fees': 'sum', 
                'total_add_fees': 'sum', 'net_settled_amount': 'sum'
            }).reset_index()
            
            # Yahan par maine symbol hata kar sirf numeric numbers rakhe hain (₹ hata diya)
            for col in ['gross_sale_amt', 'total_refund', 'marketplace_fees', 'total_add_fees', 'net_settled_amount']:
                display_df[col] = display_df[col].round(2)
                
            st.dataframe(display_df, use_container_width=True, height=400)
        else:
            st.info("No records found. Please upload your Excel sheet via the 'Upload Data' tab first!")
    except Exception as e:
        st.error(f"Error rendering metrics dashboard: {str(e)}")
