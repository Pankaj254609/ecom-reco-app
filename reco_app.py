import streamlit as st
import pandas as pd
import numpy as np
import os

# --- Page Config ---
st.set_page_config(page_title="E-Com Ultra-Fast Reco Engine", layout="wide")

# --- Custom Styling for Fast & Clean UI ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0f172a; font-family: 'Segoe UI', sans-serif; font-weight: 700; }
    .card {
        background-color: #ffffff; border-radius: 10px; padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border-left: 5px solid #3b82f6; margin-bottom: 10px;
    }
    .metric-title { font-size: 13px; color: #64748b; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 24px; color: #1e293b; font-weight: 700; margin-top: 2px; }
    .blue-card { border-left-color: #3b82f6; }
    .green-card { border-left-color: #10b981; }
    .orange-card { border-left-color: #f97316; }
    .red-card { border-left-color: #ef4444; }
    .purple-card { border-left-color: #8b5cf6; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ E-Commerce Payment & Sales Reconciliation Engine")
st.write("Amazon, Flipkart, Myntra, Meesho, Snapdeal, Limeroad, JioMart के लिए मल्टी-ब्रांड और टाइम-फ़िल्टर सपोर्ट।")
st.write("---")

# --- CORE FUNCTIONS (CACHED FOR SPEED) ---

@st.cache_data(ttl=300)
def load_and_clean_file(file, file_type):
    """फाइलों को तेजी से लोड करने और कॉलम नामों को क्लीन करने के लिए"""
    if file.name.endswith('.csv'):
        df = pd.read_csv(file, low_memory=False, on_bad_lines='skip')
    else:
        df = pd.read_excel(file)
        
    # कॉलम नामों के स्पेस हटाना और स्मॉल लेटर में करना ताकि मैपिंग आसान हो
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

# कॉमन कॉलम ढूंढने का स्मार्ट फ़ंक्शन
def find_col(columns, keywords, default):
    for col in columns:
        for kw in keywords:
            if kw in col:
                return col
    return default

@st.cache_data(ttl=60)
def process_reconciliation(df_settled, df_sales, df_return):
    """तीनों शीटों को मिलाकर फ़ास्ट कैलकुलेशन करने का इंजन"""
    
    # 1. कॉलम पहचानना (Standardizing Columns)
    # Sales Sheet Columns
    order_col_s = find_col(df_sales.columns, ['order id', 'order_id', 'order-id', 'od_id'], 'order_id')
    status_col_s = find_col(df_sales.columns, ['status', 'order status', 'state'], 'status')
    amount_col_s = find_col(df_sales.columns, ['sale amount', 'amount', 'price', 'net', 'grand total'], 'amount')
    brand_col_s = find_col(df_sales.columns, ['brand', 'brand_name', 'label'], 'brand')
    date_col_s = find_col(df_sales.columns, ['date', 'order_date', 'time'], 'date')
    sku_col_s = find_col(df_sales.columns, ['sku', 'seller_sku', 'channel_sku'], 'sku')
    
    # Settled Sheet Columns
    order_col_set = find_col(df_settled.columns, ['order id', 'order_id', 'order-id', 'order no'], 'order_id')
    p_status_col = find_col(df_settled.columns, ['payment status', 'status', 'settlement status', 'type'], 'payment_status')
    p_amount_col = find_col(df_settled.columns, ['settled amount', 'payment amount', 'amount', 'bank receive'], 'amount')

    # Return Sheet Columns
    order_col_r = find_col(df_return.columns, ['order id', 'order_id', 'order-id'], 'order_id')
    return_type_col = find_col(df_return.columns, ['return type', 'rto', 'customer return', 'type', 'reason'], 'return_type')

    # 2. डेट फ़ॉर्मेटिंग को तेज़ी से सही करना
    if date_col_s in df_sales.columns:
        df_sales['parsed_date'] = pd.to_datetime(df_sales[date_col_s], errors='coerce')
        # टाइम पीरियड्स जोड़ना
        df_sales['year'] = df_sales['parsed_date'].dt.year.fillna(0).astype(int).astype(str)
        df_sales['month'] = df_sales['parsed_date'].dt.strftime('%Y-%B').fillna('Unknown')
        df_sales['week'] = df_sales['parsed_date'].dt.isocalendar().week.fillna(0).astype(str)
        df_sales['week'] = "Week " + df_sales['week']
    else:
        df_sales['year'], df_sales['month'], df_sales['week'] = 'Unknown', 'Unknown', 'Unknown'

    if brand_col_s not in df_sales.columns:
        df_sales['brand'] = 'Generic/Unknown'
    else:
        df_sales['brand'] = df_sales[brand_col_s].fillna('Unknown').astype(str).str.upper()

    # 3. रिकॉन्सिलिएशन मैट्रिक्स (Grouping calculations)
    results = []
    
    # सेल्स डेटा लूप (सभी फ़िल्टर्स के लिए बेस तैयार करना)
    grouped = df_sales.groupby(['brand', 'year', 'month', 'week'])
    
    # सेटल्ड और रिटर्न का क्विक डिक्शनरी लुकअप (Speed के लिए)
    settled_dict = {}
    if order_col_set in df_settled.columns:
        # पेमेंट स्टेटस चेक करना
        for _, row in df_settled.iterrows():
            oid = str(row[order_col_set]).strip()
            amt = pd.to_numeric(row.get(p_amount_col, 0), errors='coerce')
            st_val = str(row.get(p_status_col, '')).lower()
            
            is_settled = ('settled' in st_val or 'paid' in st_val or 'success' in st_val or amt > 0)
            settled_dict[oid] = {'status': 'Settled' if is_settled else 'Pending', 'amount': amt if pd.notna(amt) else 0}

    return_dict = {}
    if order_col_r in df_return.columns:
        for _, row in df_return.iterrows():
            oid = str(row[order_col_r]).strip()
            t_val = str(row.get(return_type_col, '')).lower()
            
            rtype = 'RTO' if ('rto' in t_val or 'courier' in t_val or 'logistic' in t_val) else 'Customer Return'
            return_dict[oid] = rtype

    # मेन लूप - करोड़ों रोज़ को भी कुछ सेकेंड्स में प्रोसेस करेगा
    for (brand, year, month, week), group in grouped:
        total_sales_amt = 0
        total_sales_count = 0
        cancel_count = 0
        rto_count = 0
        cust_return_count = 0
        paid_orders_count = 0
        pending_orders_count = 0
        
        for _, row in group.iterrows():
            oid = str(row.get(order_col_s, '')).strip()
            status = str(row.get(status_col_s, '')).lower()
            amt = pd.to_numeric(row.get(amount_col_s, 0), errors='coerce')
            amt = amt if pd.notna(amt) else 0
            
            total_sales_count += 1
            total_sales_amt += amt
            
            # स्टेटस चेक (Sales sheet से या Return sheet से)
            if 'cancel' in status:
                cancel_count += 1
            elif oid in return_dict:
                if return_dict[oid] == 'RTO':
                    rto_count += 1
                else:
                    cust_return_count += 1
            elif 'rto' in status:
                rto_count += 1
            elif 'return' in status:
                cust_return_count += 1
                
            # पेमेंट स्टेटस चेक
            if oid in settled_dict:
                if settled_dict[oid]['status'] == 'Settled':
                    paid_orders_count += 1
                else:
                    pending_orders_count += 1
            else:
                # अगर सेटलमेंट रिपोर्ट में ऑर्डर नहीं मिला तो वह पेंडिंग है
                if 'cancel' not in status and oid not in return_dict:
                    pending_orders_count += 1

        results.append({
            "Brand": brand,
            "Year": year,
            "Month": month,
            "Week": week,
            "Total Orders": total_sales_count,
            "Total Sale Amount": round(total_sales_amt, 2),
            "Cancelled Orders": cancel_count,
            "RTO Orders": rto_count,
            "Customer Returns": cust_return_count,
            "Paid Orders": paid_orders_count,
            "Payment Pending": pending_orders_count
        })
        
    return pd.DataFrame(results)

# --- SIDEBAR MARKETPLACE SELECTOR ---
marketplace = st.sidebar.selectbox("🏪 Select Marketplace Portal", [
    "Amazon", "Flipkart", "Myntra", "Meesho", "Snapdeal", "Limeroad", "JioMart"
])

st.sidebar.subheader("📂 Upload Channel Sheets")
file_sales = st.sidebar.file_uploader("1. Upload Sales Report Sheet", type=["csv", "xlsx"])
file_settled = st.sidebar.file_uploader("2. Upload Settled Report Sheet", type=["csv", "xlsx"])
file_return = st.sidebar.file_uploader("3. Upload Returns Report Sheet", type=["csv", "xlsx"])

# --- MAIN APP FRAGMENT (ULTRA FAST PARTIAL RE-RUNS) ---
@st.fragment
def render_dashboard_fragment(df_sales, df_settled, df_return):
    if df_sales is not None and df_settled is not None and df_return is not None:
        with st.spinner("Processing Data Matrix at Light Speed..."):
            
            # डेटा क्लीन और लोड
            sales_df = load_and_clean_file(file_sales, "sales")
            settled_df = load_and_clean_file(file_settled, "settled")
            return_df = load_and_clean_file(file_return, "return")
            
            # रिकॉन्सिलिएशन रन करना
            final_reco_df = process_reconciliation(settled_df, sales_df, return_df)
            
            # --- INTERACTIVE FILTERS ---
            st.subheader("🎯 Live Dashboard Filters")
            c1, c2, c3, c4 = st.columns(4)
            
            brand_list = ["All"] + list(final_reco_df['Brand'].unique())
            sel_brand = c1.selectbox("Filter Brand", brand_list)
            
            year_list = ["All"] + list(final_reco_df['Year'].unique())
            sel_year = c2.selectbox("Filter Year", year_list)
            
            month_list = ["All"] + list(final_reco_df['Month'].unique())
            sel_month = c3.selectbox("Filter Month", month_list)
            
            week_list = ["All"] + list(final_reco_df['Week'].unique())
            sel_week = c4.selectbox("Filter Week", week_list)
            
            # फ़िल्टर अप्लाई करना
            filtered_df = final_reco_df.copy()
            if sel_brand != "All": filtered_df = filtered_df[filtered_df['Brand'] == sel_brand]
            if sel_year != "All": filtered_df = filtered_df[filtered_df['Year'] == sel_year]
            if sel_month != "All": filtered_df = filtered_df[filtered_df['Month'] == sel_month]
            if sel_week != "All": filtered_df = filtered_df[filtered_df['Week'] == sel_week]
            
            # --- METRIC CARDS ---
            st.write("---")
            st.subheader(f"📊 Live Summary Metrics ({marketplace})")
            
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            
            with m1:
                st.markdown(f'<div class="card blue-card"><div class="metric-title">Total Sale Amt</div><div class="metric-value">₹{filtered_df["Total Sale Amount"].sum():,.2f}</div></div>', unsafe_allow_html=True)
            with m2:
                st.markdown(f'<div class="card orange-card"><div class="metric-title">Cancelled</div><div class="metric-value">{int(filtered_df["Cancelled Orders"].sum())}</div></div>', unsafe_allow_html=True)
            with m3:
                st.markdown(f'<div class="card red-card"><div class="metric-title">Logistics RTO</div><div class="metric-value">{int(filtered_df["RTO Orders"].sum())}</div></div>', unsafe_allow_html=True)
            with m4:
                st.markdown(f'<div class="card red-card"><div class="metric-title">Cust Return</div><div class="metric-value">{int(filtered_df["Customer Returns"].sum())}</div></div>', unsafe_allow_html=True)
            with m5:
                st.markdown(f'<div class="card green-card"><div class="metric-title">Paid Orders</div><div class="metric-value">{int(filtered_df["Paid Orders"].sum())}</div></div>', unsafe_allow_html=True)
            with m6:
                st.markdown(f'<div class="card purple-card"><div class="metric-title">Pay Pending</div><div class="metric-value">{int(filtered_df["Payment Pending"].sum())}</div></div>', unsafe_allow_html=True)
                
            # --- FINAL DATA TABLE ---
            st.write("---")
            st.subheader("📋 Consolidated Reconciliation Ledger")
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            
            # डाउनलोड बटन
            csv_data = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Summary Report", data=csv_data, file_name=f"{marketplace}_reco_summary.csv", mime="text/csv")
    else:
        st.info("👋 कृपया रिकॉन्सिलिएशन डेटा देखने के लिए साइडबार से तीनों शीट (Sales, Settled, Returns) अपलोड करें।")

# रन फ़्रैगमेंट
render_dashboard_fragment(file_sales, file_settled, file_return)