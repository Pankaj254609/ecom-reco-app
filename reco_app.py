import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Flipkart SKU Wise Reconciliation", layout="wide")
st.title("📊 Flipkart Order Item ID & SKU Wise Real Settlement Summary")

# --- Custom Global UI Styling (Uniform #46bdc6 Color Style) ---
st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        background-color: #46bdc6 !important;
        padding: 15px !important;
        border-radius: 8px !important;
        border: 1px solid #3197a0 !important;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
        color: black !important;
    }
    div[data-testid="stDataFrame"] table th {
        background-color: #46bdc6 !important;
        color: black !important;
        font-weight: bold !important;
        border: 1px solid #3197a0 !important;
        text-align: center !important;
    }
    div[data-testid="stDataFrame"] table td {
        border: 1px solid #3197a0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Helper to Clean Numbers Safely ---
def get_num_val(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).replace('₹', '').replace(',', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0

# --- ADVANCED FLIPKART SKU & ORDER ITEM ID PROCESSOR ---
def process_flipkart_sku_wise(df):
    # Fix the Unnamed Column / Top Row Offset Problem dynamically
    # Agar pehle column me 'payment' ya 'summary' jaisa metadata ho, to real header dhundhein
    if df.shape[0] > 0:
        for i in range(min(15, len(df))):
            row_values = [str(x).lower().strip() for x in df.iloc[i].dropna()]
            if 'order item id' in row_values or 'order id' in row_values or 'quantity' in row_values:
                # Set this row as the true header
                df.columns = [str(c).strip() for c in df.iloc[i]]
                df = df.iloc[i+1:].reset_index(drop=True)
                break

    # Clean Column Names again after shifting
    df.columns = [str(c).strip() for c in df.columns]
    col_mapping = {c.lower(): c for c in df.columns}
    
    # Target exact structural columns
    qty_col = col_mapping.get('quantity', None)
    sale_col = col_mapping.get('sale amount (rs.)', col_mapping.get('sale amount', None))
    refund_col = col_mapping.get('refund (rs.)', col_mapping.get('refund', None))
    fee_col = col_mapping.get('marketplace fee (rs.)', col_mapping.get('marketplace fee', None))
    tax_col = col_mapping.get('taxes (rs.)', col_mapping.get('taxes', None))
    add_col = col_mapping.get('offer adjustments (rs.)', col_mapping.get('offer adjustments', col_mapping.get('settlement value add', None)))
    settle_col = col_mapping.get('bank settlement value (rs.)', col_mapping.get('bank settlement value', col_mapping.get('bank settlement', None)))
    
    order_item_col = col_mapping.get('order item id', None)
    sku_col = col_mapping.get('seller sku', col_mapping.get('sku', None))
    return_type_col = col_mapping.get('return type', None)

    # Secondary Check if still not found
    if not qty_col or not order_item_col:
        st.error(f"⚠️ **Error:** Is sheet ke true headers system match nahi kar paa raha hai. Kripya check karein ki aapne sahi sheet upload ki hai. Columns mile: {list(df.columns)[:8]}")
        st.stop()

    # 1. Clean the essential numeric columns
    df['Clean_Qty'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int)
    df['Clean_Sale'] = df[sale_col].apply(get_num_val) if sale_col else 0.0
    df['Clean_Refund'] = df[refund_col].apply(get_num_val) if refund_col else 0.0
    df['Clean_Fee'] = df[fee_col].apply(get_num_val) if fee_col else 0.0
    df['Clean_Tax'] = df[tax_col].apply(get_num_val) if tax_col else 0.0
    df['Clean_Add'] = df[add_col].apply(get_num_val) if add_col else 0.0
    df['Clean_Settle'] = df[settle_col].apply(get_num_val) if settle_col else 0.0
    
    # 2. Extract Return Categories
    df['Temp_Return'] = df[return_type_col].fillna('NA').astype(str).str.strip().str.upper() if return_type_col else 'NA'
    
    # Calculate conditional units logic
    df['Is_Sale'] = np.where((df['Temp_Return'] == 'NA') & (df['Clean_Qty'] > 0), df['Clean_Qty'], 0)
    df['Logistics_Return'] = np.where(df['Temp_Return'].str.contains('RTO|DTO|COURIER', case=False, na=False), df['Clean_Qty'], 0)
    df['Customer_Return'] = np.where(df['Temp_Return'].str.contains('CUSTOMER', case=False, na=False), df['Clean_Qty'], 0)
    
    # 3. Group by Order Item ID and SKU to blend 0-180 INR rows
    group_keys = [df[order_item_col], df[sku_col] if sku_col else df[order_item_col]]
    
    sku_summary = df.groupby(group_keys).agg({
        'Is_Sale': 'sum',
        'Logistics_Return': 'sum',
        'Customer_Return': 'sum',
        'Clean_Sale': 'sum',
        'Clean_Refund': 'sum',
        'Clean_Fee': 'sum',
        'Clean_Tax': 'sum',
        'Clean_Add': 'sum',
        'Clean_Settle': 'sum'
    }).reset_index()
    
    # Rename for professional UI presentation
    sku_summary.columns = [
        'Order Item ID', 'Seller SKU', 'Total Sale Qty', 'Total Logistics Return Qty', 
        'Total Customer Return Qty', 'Gross Sale Amt', 'Total Refund', 
        'Marketplace Fees', 'Taxes', 'Total ADD Fees', 'Net Settled Amount'
    ]
    
    return sku_summary

# --- Sidebar Uploading Panel ---
st.sidebar.markdown("## 📤 Sheet Upload Panel")
uploaded_file = st.sidebar.file_uploader("Flipkart 'Orders' Sheet CSV Upload Karein", type=["csv", "xlsx"])

# --- Main Logic Dashboard ---
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, low_memory=False)
        else:
            df_raw = pd.read_excel(uploaded_file)
            
        # Running the dynamic item-sku processor
        processed_report = process_flipkart_sku_wise(df_raw)
        
        # Show Highlighted Metrics Cards
        st.markdown("### 📈 Consolidated Performance KPI Dashboard")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Gross Sales", f"₹{processed_report['Gross Sale Amt'].sum():,.2f}")
        k2.metric("Net Settled Amount", f"₹{processed_report['Net Settled Amount'].sum():,.2f}")
        k3.metric("Logistics Return Pcs", f"{int(processed_report['Total Logistics Return Qty'].sum())} Pcs")
        k4.metric("Customer Return Pcs", f"{int(processed_report['Total Customer Return Qty'].sum())} Pcs")
        
        st.write("---")
        
        # Injecting Bottom TOTAL Row dynamically
        total_row = pd.DataFrame([{
            'Order Item ID': 'TOTAL', 'Seller SKU': '',
            'Total Sale Qty': processed_report['Total Sale Qty'].sum(),
            'Total Logistics Return Qty': processed_report['Total Logistics Return Qty'].sum(),
            'Total Customer Return Qty': processed_report['Total Customer Return Qty'].sum(),
            'Gross Sale Amt': processed_report['Gross Sale Amt'].sum(),
            'Total Refund': processed_report['Total Refund'].sum(),
            'Marketplace Fees': processed_report['Marketplace Fees'].sum(),
            'Taxes': processed_report['Taxes'].sum(),
            'Total ADD Fees': processed_report['Total ADD Fees'].sum(),
            'Net Settled Amount': processed_report['Net Settled Amount'].sum()
        }])
        
        display_df = pd.concat([processed_report, total_row], ignore_index=True)
        
        # Pure Uniform #46bdc6 Color Style formatting logic 
        def style_full_table(df):
            return df.style.apply(lambda x: pd.DataFrame([['background-color: #46bdc6; color: black; font-weight: bold;'] * len(df.columns)], index=df.index, columns=df.columns), axis=None)
        
        fmt = {
            'Gross Sale Amt': '₹{:,.2f}', 'Total Refund': '₹{:,.2f}', 'Marketplace Fees': '₹{:,.2f}',
            'Taxes': '₹{:,.2f}', 'Total ADD Fees': '₹{:,.2f}', 'Net Settled Amount': '₹{:,.2f}',
            'Total Sale Qty': '{:,.0f}', 'Total Logistics Return Qty': '{:,.0f}', 'Total Customer Return Qty': '{:,.0f}'
        }
        
        styled_final = style_full_table(display_df).format(fmt)
        
        # Display live grid layout
        st.subheader("📋 SKU & Order Item ID Wise Consolidated Sheet Ledger")
        st.dataframe(styled_final, use_container_width=True, hide_index=True)
        
        # Single click download option
        st.download_button(
            label="📥 Download Reconciled SKU Sheet",
            data=processed_report.to_csv(index=False).encode('utf-8'),
            file_name='Flipkart_SKU_Wise_Clean_Settlement.csv',
            mime='text/csv'
        )
            
    except Exception as e:
        st.error(f"Sheet load karne ya processing mein error aaya: {str(e)}")
else:
    st.info("Kripya side panel se apni Flipkart ki payment sheet upload karein.")
