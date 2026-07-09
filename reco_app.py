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

df_design = load_cloud_data()

# --- Sidebar Controls ---
st.sidebar.markdown("<h2>🎯 Data Upload & Filters</h2>", unsafe_allow_html=True)

st.sidebar.subheader("📤 New Sheet Upload")
uploaded_file = st.sidebar.file_uploader("Excel file upload karein", type=["xlsx"])

if uploaded_file is not None:
    if st.sidebar.button("🚀 Push to Online Cloud DB"):
        with st.spinner("Data online save ho raha hai..."):
            try:
                # Excel file ki saari sheets ke naam check karna
                xl = pd.ExcelFile(uploaded_file)
                sheet_names = xl.sheet_names
                
                # 'DESIGN WISE' naam dhoondna (chahe space ho ya chote-bade akshar hon)
                target_sheet = None
                for s in sheet_names:
                    if "DESIGN" in s.upper():
                        target_sheet = s
                        break
                
                if not target_sheet:
                    st.sidebar.error("Excel Sheet mein 'DESIGN WISE' naam ki koi sheet nahi mili!")
                else:
                    df_excel = pd.read_excel(uploaded_file, sheet_name=target_sheet)
                    df_excel.columns = [str(c).strip() for c in df_excel.columns]
                    
                    # Agar table ke pehle column ka naam alag ho toh use stable karna
                    if len(df_excel.columns) >= 3:
                        # Pehle 3 columns ko standardized name dena backup ke liye
                        df_excel = df_excel.rename(columns={
                            df_excel.columns[0]: "Month",
                            df_excel.columns[1]: "Marketplace",
                            df_excel.columns[2]: "Design"
                        })
                    
                    # Data Cleaning: Faltu ya repeat hone wali headers lines ko hatana
                    df_excel = df_excel[df_excel['Month'].notna()]
                    df_excel = df_excel[df_excel['Month'].astype(str).str.strip() != 'Month']
                    df_excel = df_excel[df_excel['Marketplace'].astype(str).str.strip() != 'Sale Amount']
                    
                    # Numeric columns handle karna
                    num_cols_map = {
                        "Sale Amount": "Sale Amount", "Selling Price": "SELLING PRICE", 
                        "Marketplace Fee": "Marketplace Fee", "Taxes": "Taxes", 
                        "Protection Fund": "Protection Fund", "Refund (Rs.)": "Refund (Rs.)", 
                        "Gross Sale": "GROSS SALE", "DEL": "DEL", "DTO": "DTO", "RTO": "RTO", 
                        "Actual": "ACTUAL", "Input GST + TCS Credits": "Input GST + TCS Credits", 
                        "Bank Settlement": "Bank Settlement", "Settlement Value ADD": "Settlement Value ADD", 
                        "Final Settled Amt.": "FINAL SETTELED AMT.", "Cost Price": "COST PRICE"
                    }
                    
                    db_records = []
                    for _, row in df_excel.iterrows():
                        # Agar Design name blank ya header jaisa lag raha ho toh skip karein
                        dsgn = str(row.get("Design", "")).strip()
                        if dsgn == "" or "DESIGN" in dsgn.upper() or "SELLING" in dsgn.upper():
                            continue
                            
                        def get_num(col_keys):
                            for k in col_keys:
                                if k in row and pd.notna(row[k]):
                                    val = str(row[k]).replace('₹', '').replace(',', '').strip()
                                    try: return float(val)
                                    except: pass
                            return 0.0

                        db_records.append({
                            "month": str(row.get("Month", "")).strip(),
                            "marketplace": str(row.get("Marketplace", "")).strip(),
                            "design": dsgn,
                            "sale_amount": get_num(["Sale Amount"]),
                            "selling_price": get_num(["Selling Price", "SELLING PRICE"]),
                            "marketplace_fee": get_num(["Marketplace Fee"]),
                            "taxes": get_num(["Taxes"]),
                            "protection_fund": get_num(["Protection Fund"]),
                            "refund_rs": get_num(["Refund (Rs.)"]),
                            "gross_sale": get_num(["Gross Sale", "GROSS SALE"]),
                            "del_qty": int(get_num(["DEL"])),
                            "dto_qty": int(get_num(["DTO"])),
                            "rto_qty": int(get_num(["RTO"])),
                            "actual_qty": int(get_num(["Actual", "ACTUAL"])),
                            "gst_tcs_credits": get_num(["Input GST + TCS Credits"]),
                            "bank_settlement": get_num(["Bank Settlement"]),
                            "settlement_value_add": get_num(["Settlement Value ADD"]),
                            "final_settled_amt": get_num(["Final Settled Amt.", "FINAL SETTELED AMT."]),
                            "cost_price": get_num(["Cost Price", "COST PRICE"])
                        })
                    
                    if db_records:
                        # Purana dump clean karke fresh overwrite online safe push
                        supabase.table("design_wise_summary").delete().neq("month", "dummy_delete_all").execute()
                        supabase.table("design_wise_summary").insert(db_records).execute()
                        st.cache_data.clear()
                        st.sidebar.success("Data successfully cloud database par update ho gaya!")
                        st.rerun()
                    else:
                        st.sidebar.warning("Sheet se koi valid records nahi mile.")
            except Exception as e:
                st.sidebar.error(f"Upload fail hua: {e}")

st.sidebar.write("---")
st.sidebar.subheader("🔍 Data Filters")

# --- Interactive View Logic ---
if not df_design.empty:
    months = ["All"] + sorted(list(df_design["Month"].dropna().unique()))
    selected_month = st.sidebar.selectbox("Month Filter:", months)

    marketplaces = ["All"] + sorted(list(df_design["Marketplace"].dropna().unique()))
    selected_mp = st.sidebar.selectbox("Marketplace Filter:", marketplaces)

    designs = ["All"] + sorted(list(df_design["Design"].dropna().unique()))
    selected_design = st.sidebar.selectbox("Design Filter:", designs)

    filtered_df = df_design.copy()
    if selected_month != "All": filtered_df = filtered_df[filtered_df["Month"] == selected_month]
    if selected_mp != "All": filtered_df = filtered_df[filtered_df["Marketplace"] == selected_mp]
    if selected_design != "All": filtered_df = filtered_df[filtered_df["Design"] == selected_design]

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
    
    fmt_dict = {
        'Sale Amount': '₹{:,.2f}', 'Selling Price': '₹{:,.2f}', 'Marketplace Fee': '₹{:,.2f}',
        'Taxes': '₹{:,.2f}', 'Protection Fund': '₹{:,.2f}', 'Refund (Rs.)': '₹{:,.2f}',
        'Gross Sale': '₹{:,.2f}', 'Input GST + TCS Credits': '₹{:,.2f}', 'Bank Settlement': '₹{:,.2f}',
        'Settlement Value ADD': '₹{:,.2f}', 'Final Settled Amt.': '₹{:,.2f}', 'Cost Price': '₹{:,.2f}'
    }
    available_fmt = {k: v for k, v in fmt_dict.items() if k in filtered_df.columns}
    st.dataframe(filtered_df.style.format(available_fmt), use_container_width=True, hide_index=True)

    st.download_button(
        label="📥 Download This Filtered Design-Wise Summary",
        data=filtered_df.to_csv(index=False).encode('utf-8'),
        file_name='Design_Wise_Summary_Report.csv',
        mime='text/csv',
    )
else:
    st.info("Database khali hai! Kripya side panel ka use karke apni 'DESIGN WISE' excel sheet upload karein.")
