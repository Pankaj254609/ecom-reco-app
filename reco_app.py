import streamlit as st
import pandas as pd

# Page Configuration
st.set_page_config(page_title="E-Commerce ReconcilePro", layout="wide")

# Sidebar Menu
st.sidebar.title("MAIN MENU")
menu = st.sidebar.radio("Go to", ["Dashboard", "Reco Summary", "Manual Sheet", "Reconciliation"])

if menu == "Dashboard" or menu == "Reco Summary":
    st.title("Reconciliation Summary")
    st.write("Single-glance overview of sales, returns, settlements, taxes, pending and mismatches.")
    
    # File Uploader for Marketplace Data
    uploaded_file = st.file_uploader("Upload Amazon/Flipkart CSV or Excel File", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        # Read File
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success("File successfully uploaded!")
        
        # Display sample data
        st.subheader("Raw Data Preview")
        st.dataframe(df.head())
        
        # Dummy/Calculated Metrics (Aapke data columns ke mutabiq adjust ho sakta hai)
        gross_sales = 586869
        returns_amt = 71136
        bank_received = 254664.38
        total_deductions = -155143.40
        mismatch_amt = 151801.98
        
        # Display Summary Cards (Metric Cards)
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Gross Sales", f"₹{gross_sales:,}")
        with col2:
            st.metric("Returns", f"₹{returns_amt:,}", "-12.12% of sales")
        with col3:
            st.metric("Bank Received", f"₹{bank_received:,.2f}", "49.38% of net sales")
        with col4:
            st.metric("Total Deductions", f"₹{total_deductions:,.2f}", "-30.08% of net sales")
        with col5:
            st.metric("Mismatch Amount", f"₹{mismatch_amt:,.2f}", "276 mismatch orders")
            
        # Export Button
        st.download_button(
            label="Export Summary",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name='reconciliation_summary.csv',
            mime='text/csv'
        )
    else:
        st.info("Kripya upar diye gaye button se apni Excel ya CSV file upload karein.")

elif menu == "Manual Sheet":
    st.title("Manual Sheet Management")
    st.write("Yahan aap manual entries ya mapping manage kar sakte hain.")

elif menu == "Reconciliation":
    st.title("Reconciliation Engine")
    st.write("Expected vs Actual settlement matching yahan hogi.")
