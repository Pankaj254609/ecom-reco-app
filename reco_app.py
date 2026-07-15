import streamlit as st
import pandas as pd
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Flipkart SKU Wise Reconciliation", layout="wide")
st.title("📊 Flipkart Order Item ID & SKU Wise Real Settlement Summary")

# --- Custom Global UI Styling (#46bdc6 Style) ---
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
    # STEP 1: Dynamic Row Skipping Logic (Unnamed Columns Fix)
    # Agar row 0 ya uske baad wale rows me metadata hai, toh scan karke real header row nikalenge
    header_found = False
    for i in range(min(20, len(df))):
        row_str = [str(x).lower().strip() for x in df.iloc[i].dropna().values]
        # Check standard flipkart keys inside any column
        if any('order item id' in x or 'order_item_id' in x or 'quantity' in x or 'sale amount' in x for x in row_str):
            df.columns = [str(c).strip() for c in df.iloc[i]]
            df = df.iloc[i+1:].reset_index(drop=True)
            header_found = True
            break
            
    # Agar direct fix nahi hua, toh search fallback
    if not header_found:
        # Pata lagao kis row me column names jaisa valid content hai
        for col in df.columns:
            if df[col].astype(str).str.contains('Order item ID|Quantity|Sale Amount', case=False, na=False).any():
                idx = df[df[col].astype(str).str.contains('Order item ID|Quantity|Sale Amount', case=False, na=False)].index[0]
                df.columns = [str(c).strip() for c in df.iloc[idx]]
                df = df.iloc[idx+1:].reset_index(drop=True)
                break

    # Clean text columns name mappings
    df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
    col_mapping = {c.lower(): c for c in df.columns}
    
    # Resolving structural column names dynamically
    qty_col = next((col_mapping[k] for k in col_mapping if 'quantity' in k), None)
    sale_col = next((col_mapping[k] for k in col_mapping if 'sale amount' in k), None)
    refund_col = next((col_mapping[k] for k in col_mapping if 'refund' in k), None)
    fee_col = next((col_mapping[k] for k in col_mapping if 'marketplace fee' in k), None)
    tax_col = next((col_mapping[k] for k in col_mapping if 'taxes' in k), None)
    add_col = next((col_mapping[k] for k in col_mapping if 'offer adjustment' in k or 'settlement value add' in k), None)
    settle_col = next((col_mapping[k] for k in col_mapping if 'bank settlement' in k or 'settled' in k), None)
    
    order_item_col = next((col_mapping[k] for k in col_mapping if 'order item id' in k or 'order_item_id' in k), None)
    sku_col = next((col_mapping[k] for k in col_mapping if 'seller sku' in k or 'sku' in k), None)
    return_type_col = next((col_mapping[k] for k in col_mapping if 'return type' in k or 'return_type' in k), None)

    # Final validation block
    if not order_item_col:
        st.error(f"❌ **Error:** System ko true columns nahi mil paye. Kripya check karein ki aapne sahi tab upload kiya hai. Columns mile: {list(df.columns)[:6]}")
        st.info("💡 **Tip:** Agar aap Excel (.xlsx) file use kar rahe hain, toh usme se **'Orders'** wale tab ko alag se CSV ya Excel banakar upload karein.")
        st.stop()

    # Clean raw numeric items
    df['Clean_Qty'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0).astype(int) if qty_col else 1
    df['Clean_Sale'] = df[sale_col].apply(get_num_val) if sale_col else 0.0
    df['Clean_Refund'] = df[refund_col].apply(get_num_val) if refund_col else 0.0
    df['Clean_Fee'] = df[fee_col].apply(get_num_val) if fee_col else 0.0
    df['Clean_Tax'] = df[tax_col].apply(get_num_val) if tax_col else 0.0
    df['Clean_Add'] = df[add_col].apply(get_num_val) if add_col else 0.0
    df['Clean_Settle'] = df[settle_col].apply(get_num_val) if settle_col else 0.0
    
    # Return types mapping logic
    df['Temp_Return'] = df[return_type_col].fillna('NA').astype(str).str.strip().str.upper() if return_type_col else 'NA'
    
    df['Is_Sale'] = np.where((df['Temp_Return'] == 'NA') | (df['Temp_Return'] == ''), df['Clean_Qty'], 0)
    df['Logistics_Return'] = np.where(df['Temp_Return'].str.contains('RTO|DTO|COURIER', case=False, na=False), df['Clean_Qty'], 0)
    df['Customer_Return'] = np.where(df['Temp_Return'].str.contains('CUSTOMER', case=False, na=False), df['Clean_Qty'], 0)
    
    # Grouping data at uniquely identified combinations
    g_sku = sku_col if sku_col else order_item_col
    sku_summary = df.groupby([df[order_item_col], df[g_sku]]).agg({
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
    
    sku_summary.columns = [
        'Order Item ID', 'Seller SKU', 'Total Sale Qty', 'Total Logistics Return Qty', 
        'Total Customer Return Qty', 'Gross Sale Amt', 'Total Refund', 
        'Marketplace Fees', 'Taxes', 'Total ADD Fees', 'Net Settled Amount'
    ]
    
    return sku_summary

# --- Sidebar Uploading Panel ---
st.sidebar.markdown("## 📤 Sheet Upload Panel")
uploaded_file = st.sidebar.file_uploader("Flipkart 'Orders' Sheet CSV Upload Karein", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        # Safely capture sheets or format types
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, low_memory=False)
        else:
            # Agar Excel upload ki hai, toh specific 'Orders' tab read karne ka try karein
            xl = pd.ExcelFile(uploaded_file)
            target_sheet = 'Orders' if 'Orders' in xl.sheet_names else xl.sheet_names[0]
            df_raw = pd.read_excel(uploaded_file, sheet_name=target_sheet)
            
        processed_report = process_flipkart_sku_wise(df_raw)
        
        # Display Metrics Block
        st.markdown("### 📈 Consolidated Performance KPI Dashboard")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Gross Sales", f"₹{processed_report['Gross Sale Amt'].sum():,.2f}")
        k2.metric("Net Settled Amount", f"₹{processed_report['Net Settled Amount'].sum():,.2f}")
        k3.metric("Logistics Return Pcs", f"{int(processed_report['Total Logistics Return Qty'].sum())} Pcs")
        k4.metric("Customer Return Pcs", f"{int(processed_report['Total Customer Return Qty'].sum())} Pcs")
        
        st.write("---")
        
        # Bottom Total Row Injection
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
        
        def style_full_table(df):
            return df.style.apply(lambda x: pd.DataFrame([['background-color: #46bdc6; color: black; font-weight: bold;'] * len(df.columns)], index=df.index, columns=df.columns), axis=None)
        
        fmt = {
            'Gross Sale Amt': '₹{:,.2f}', 'Total Refund': '₹{:,.2f}', 'Marketplace Fees': '₹{:,.2f}',
            'Taxes': '₹{:,.2f}', 'Total ADD Fees': '₹{:,.2f}', 'Net Settled Amount': '₹{:,.2f}',
            'Total Sale Qty': '{:,.0f}', 'Total Logistics Return Qty': '{:,.0f}', 'Total Customer Return Qty': '{:,.0f}'
        }
        
        styled_final = style_full_table(display_df).format(fmt)
        
        st.subheader("📋 SKU & Order Item ID Wise Consolidated Sheet Ledger")
        st.dataframe(styled_final, use_container_width=True, hide_index=True)
        
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
