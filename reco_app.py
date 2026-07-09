import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- Page Config & Theme ---
st.set_page_config(page_title="Design-Wise Summary Dashboard", layout="wide")
st.title("📆 डिज़ाइन-वाइज़ ई-कॉमर्स ओवरऑल समरी डैशबोर्ड")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0f172a; font-family: 'Segoe UI', sans-serif; font-weight: 700; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; color: #ffffff !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] h2 { color: #ffffff !important; }
    .stButton>button {
        background-color: #2563eb !important; color: white !important;
        border-radius: 6px !important; width: 100%; font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- Supabase Database Connection ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Supabase configuration secrets sahi nahi hain. Kripya st.secrets check karein.")

# --- Load Data From Online Cloud Database ---
def load_cloud_data():
    try:
        res = supabase.table("design_wise_summary").select("*").execute()
        df_cloud = pd.DataFrame(res.data)
        if not df_cloud.empty:
            # Columns rename matching original sheet format
            df_cloud = df_cloud.rename(columns={
                "month": "Month", "marketplace": "Marketplace", "design": "Design",
                "sale_amount": "Sale Amount", "selling_price": "Selling Price",
                "marketplace_fee": "Marketplace Fee", "taxes": "Taxes",
                "protection_fund": "Protection Fund", "refund_rs": "Refund (Rs.)",
                "gross_sale": "Gross Sale", "del_qty": "DEL", "dto_qty": "DTO", "rto_qty": "RTO",
                "actual_qty": "Actual", "gst_tcs_credits": "Input GST + TCS Credits",
                "bank_settlement": "Bank Settlement", "settlement_value_add": "Settlement Value ADD",
                "final_settled_amt": "Final Settled Amt.", "cost_price": "Cost Price"
            })
            return df_cloud
    except Exception as e:
        pass
    return pd.DataFrame()

# Data refresh handling
df_design = load_cloud_data()

# --- Sidebar Controls ---
st.sidebar.markdown("<h2>🎯 Data Upload & Filters</h2>", unsafe_allow_html=True)

# 📁 Part 1: Permanent Data Sync/Upload
st.sidebar.subheader("📤 New Sheet Upload")
uploaded_file = st.sidebar.file_uploader("Excel file upload karein", type=["xlsx"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Push to Online Cloud DB"):
        with st.spinner("Data online save ho raha hai..."):
            try:
                # Sirf 'DESIGN WISE' sheet load kar rahe hain
                df_excel = pd.read_excel(uploaded_file, sheet_name='DESIGN WISE')
                
                # Cleaning column names (trailing spaces etc.)
                df_excel.columns = [str(c).strip() for c in df_excel.columns]
                
                # Check mapping consistency
                required_cols = ["Month", "Marketplace", "Design"]
                if not all(col in df_excel.columns for col in required_cols):
                    st.sidebar.error("Sheet mein 'Month', 'Marketplace', ya 'Design' columns missing hain.")
                else:
                    # Filter out rows that are headers repetitions or empty
                    df_excel = df_excel[df_excel['Month'].notna() & (df_excel['Month'] != 'Month')]
                    
                    # Numeric conversions
                    num_cols = ['Sale Amount', 'Selling Price', 'Marketplace Fee', 'Taxes', 'Protection Fund', 'Refund (Rs.)', 'Gross Sale', 'DEL', 'DTO', 'RTO', 'Actual', 'Input GST + TCS Credits', 'Bank Settlement', 'Settlement Value ADD', 'Final Settled Amt.', 'Cost Price']
                    for col in num_cols:
                        if col in df_excel.columns:
                            df_excel[col] = pd.to_numeric(df_excel[col], errors='coerce').fillna(0)
                        else:
                            df_excel[col] = 0
                    
                    # Prepare records for database insertion
                    db_records = []
                    for _, row in df_excel.iterrows():
                        db_records.append({
                            "month": str(row.get("Month", "")),
                            "marketplace": str(row.get("Marketplace", "")),
                            "design": str(row.get("Design", "")),
                            "sale_amount": float(row.get("Sale Amount", 0)),
                            "selling_price": float(row.get("Selling Price", 0)),
                            "marketplace_fee": float(row.get("Marketplace Fee", 0)),
                            "taxes": float(row.get("Taxes", 0)),
                            "protection_fund": float(row.get("Protection Fund", 0)),
                            "refund_rs": float(row.get("Refund (Rs.)", 0)),
                            "gross_sale": float(row.get("Gross Sale", 0)),
                            "del_qty": int(row.get("DEL", 0)),
                            "dto_qty": int(row.get("DTO", 0)),
                            "rto_qty": int(row.get("RTO", 0)),
                            "actual_qty": int(row.get("Actual", 0)),
                            "gst_tcs_credits": float(row.get("Input GST + TCS Credits", 0)),
                            "bank_settlement": float(row.get("Bank Settlement", 0)),
                            "settlement_value_add": float(row.get("Settlement Value ADD", 0)),
                            "final_settled_amt": float(row.get("Final Settled Amt.", 0)),
                            "cost_price": float(row.get("Cost Price", 0))
                        })
                    
                    if db_records:
                        # Pehle purana record delete karenge (Over-write logic) fir fresh insert hamesha ke liye save hoga
                        supabase.table("design_wise_summary").delete().neq("month", "dummy").execute()
                        supabase.table("design_wise_summary").insert(db_records).execute()
                        st.cache_data.clear()
                        st.sidebar.success("Data permanently cloud database par secure ho gaya!")
                        st.rerun()
            except Exception as e:
                st.sidebar.error(f"Upload fail hua: {e}")

st.sidebar.write("---")
st.sidebar.subheader("🔍 Data Filters")

# --- Interactive View Logic ---
if not df_design.empty:
    # Creating Filter List
    months = ["All"] + list(df_design["Month"].dropna().unique())
    selected_month = st.sidebar.selectbox("Month Filter:", months)

    marketplaces = ["All"] + list(df_design["Marketplace"].dropna().unique())
    selected_mp = st.sidebar.selectbox("Marketplace Filter:", marketplaces)

    designs = ["All"] + list(df_design["Design"].dropna().unique())
    selected_design = st.sidebar.selectbox("Design Filter:", designs)

    # Apply Filters
    filtered_df = df_design.copy()
    if selected_month != "All":
        filtered_df = filtered_df[filtered_df["Month"] == selected_month]
    if selected_mp != "All":
        filtered_df = filtered_df[filtered_df["Marketplace"] == selected_mp]
    if selected_design != "All":
        filtered_df = filtered_df[filtered_df["Design"] == selected_design]

    # --- Metrics Section ---
    st.subheader("📋 Key Financial KPI")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gross Sale QTY (DEL)", f"{int(filtered_df['DEL'].sum())} Pcs")
    m2.metric("Total Sale Amount", f"₹{filtered_df['Sale Amount'].sum():,.2f}")
    m3.metric("Final Settled Amount", f"₹{filtered_df['Final Settled Amt.'].sum():,.2f}")
    m4.metric("Total Refund Amount", f"₹{filtered_df['Refund (Rs.)'].sum():,.2f}")

    st.write("---")
    
    # --- Data Grid View ---
    st.subheader("📊 Design Wise Ledger View")
    
    # Currency Formatting Setup
    fmt_dict = {
        'Sale Amount': '₹{:,.2f}', 'Selling Price': '₹{:,.2f}', 'Marketplace Fee': '₹{:,.2f}',
        'Taxes': '₹{:,.2f}', 'Protection Fund': '₹{:,.2f}', 'Refund (Rs.)': '₹{:,.2f}',
        'Gross Sale': '₹{:,.2f}', 'Input GST + TCS Credits': '₹{:,.2f}', 'Bank Settlement': '₹{:,.2f}',
        'Settlement Value ADD': '₹{:,.2f}', 'Final Settled Amt.': '₹{:,.2f}', 'Cost Price': '₹{:,.2f}'
    }
    
    available_fmt = {k: v for k, v in fmt_dict.items() if k in filtered_df.columns}
    st.dataframe(filtered_df.style.format(available_fmt), use_container_width=True, hide_index=True)

    # 📥 Download Option
    st.download_button(
        label="📥 Download This Filtered Design-Wise Summary",
        data=filtered_df.to_csv(index=False).encode('utf-8'),
        file_name='Design_Wise_Summary_Report.csv',
        mime='text/csv',
    )
else:
    st.info("Database khali hai! Kripya side panel ka use karke apni 'DESIGN WISE' excel sheet upload karein taaki data cloud par permanently save ho sake.")
