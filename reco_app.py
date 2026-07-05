import streamlit as st
import pandas as pd

st.set_page_config(page_title="E-com Advanced Reco Summary", layout="wide")
st.title("📊 एडवांस ई-कॉमर्स ओवरऑल समरी डैशबोर्ड")

uploaded_file = st.file_uploader("अपनी पीएंडएल (P&L) एक्सेल शीट अपलोड करें", type=["xlsx"])

if uploaded_file is not None:
    # 'Orders P&L' शीट को लोड करना (रो 1 से डेटा शुरू हो रहा है क्योंकि रो 0 में हेडर ब्रेकअप है)
    try:
        df = pd.read_excel(uploaded_file, sheet_name='Orders P&L', skiprows=1)
        st.success("Orders P&L डेटा सफलतापूर्वक लोड हो गया है!")
    except Exception as e:
        st.error(f"शीट लोड करने में समस्या आई: {e}. कृपया सुनिश्चित करें कि शीट का नाम 'Orders P&L' है।")
        st.stop()

    # ---- डेटा क्लीनिंग और नए कॉलम्स बनाना ----
    # 1. तारीख (Order Date) को सही करना
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
        df = df.dropna(subset=['Order Date'])
        df['Year'] = df['Order Date'].dt.year
        df['Month'] = df['Order Date'].dt.strftime('%B') # Month Name
    else:
        st.error("शीट में 'Order Date' कॉलम नहीं मिला।")
        st.stop()

    # 2. ऑटोमैटिक ब्रांड निकालना (SKU Name के पहले हिस्से से)
    if 'SKU Name' in df.columns:
        df['Brand'] = df['SKU Name'].astype(str).apply(lambda x: x.split('-')[0].strip() if '-' in x else 'UNKNOWN')
    else:
        df['Brand'] = 'UNKNOWN'

    # 3. मार्केटप्लेस (Channel of Sale)
    if 'Channel of Sale' not in df.columns:
        df['Channel of Sale'] = 'Unknown Marketplace'

    # 4. जरूरी अमाउंट कॉलम्स को नंबर्स में बदलना
    amt_cols = ['Order Item Value', 'Estimated Net Sales (INR)', 'Total Expenses (INR)', 'Net Earnings (INR)', 'Amount Settled (INR)', 'Amount Pending (INR)']
    for col in amt_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    # ---- फिल्टर सेक्शन्स (Sidebar) ----
    st.sidebar.header("🎯 डेटा फ़िल्टर्स")
    
    # मार्केटप्लेस फ़िल्टर
    marketplaces = ['सब (All)'] + list(df['Channel of Sale'].unique())
    selected_mp = st.sidebar.selectbox("मार्केटप्लेस चुनें", marketplaces)
    
    # ब्रांड फ़िल्टर
    brands = ['सब (All)'] + list(df['Brand'].unique())
    selected_brand = st.sidebar.selectbox("ब्रांड चुनें", brands)
    
    # साल और महीना फ़िल्टर
    years = ['सब (All)'] + list(df['Year'].unique())
    selected_year = st.sidebar.selectbox("साल चुनें", years)
    
    months = ['सब (All)'] + list(df['Month'].unique())
    selected_month = st.sidebar.selectbox("महीना चुनें", months)

    # फ़िल्टर अप्लाई करना
    filtered_df = df.copy()
    if selected_mp != 'सब (All)': filtered_df = filtered_df[filtered_df['Channel of Sale'] == selected_mp]
    if selected_brand != 'सब (All)': filtered_df = filtered_df[filtered_df['Brand'] == selected_brand]
    if selected_year != 'सब (All)': filtered_df = filtered_df[filtered_df['Year'] == selected_year]
    if selected_month != 'सब (All)': filtered_df = filtered_df[filtered_df['Month'] == selected_month]

    # ---- मुख्य समरी डैशबोर्ड (Overall Summary Style) ----
    st.subheader("📈 ओवरऑल पीएंडएल समरी (Overall P&L Summary)")
    
    total_sales = filtered_df['Order Item Value'].sum()
    net_sales = filtered_df['Estimated Net Sales (INR)'].sum()
    total_exp = filtered_df['Total Expenses (INR)'].sum()
    net_earnings = filtered_df['Net Earnings (INR)'].sum()
    settled = filtered_df['Amount Settled (INR)'].sum()
    pending = filtered_df['Amount Pending (INR)'].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("कुल ग्रॉस सेल (Gross Sales)", f"₹{total_sales:,.2f}")
    m2.metric("नेट सेल्स (Net Sales)", f"₹{net_sales:,.2f}")
    m3.metric("कुल खर्चे (Total Expenses)", f"₹{total_exp:,.2f}")
    m4.metric("शुद्ध कमाई (Net Earnings)", f"₹{net_earnings:,.2f}")
    
    s1, s2 = st.columns(2)
    s1.metric("सेटल हो चुका अमाउंट (Settled)", f"₹{settled:,.2f}", delta="Bank Transferred")
    s2.metric("पेंडिंग अमाउंट (Pending)", f"₹{pending:,.2f}", delta="- Waiting", delta_color="inverse")

    # ---- ग्रुप-वाइज डायनामिक रिपोर्ट्स (जैसा आपको चाहिए) ----
    st.markdown("---")
    st.subheader("🗂️ कस्टमाइज्ड ग्रुप रिपोर्ट (Group-wise Summary)")
    
    group_option = st.selectbox("रिपोर्ट का आधार चुनें:", 
                                  ["Marketplace-wise", "Brand-wise", "Month-wise", "Year-wise", "Marketplace + Brand-wise"])

    if group_option == "Marketplace-wise":
        groupby_cols = ['Channel of Sale']
    elif group_option == "Brand-wise":
        groupby_cols = ['Brand']
    elif group_option == "Month-wise":
        groupby_cols = ['Year', 'Month']
    elif group_option == "Year-wise":
        groupby_cols = ['Year']
    else:
        groupby_cols = ['Channel of Sale', 'Brand']

    # ग्रुप समरी टेबल बनाना
    summary_table = filtered_df.groupby(groupby_cols).agg({
        'Order Item Value': 'sum',
        'Estimated Net Sales (INR)': 'sum',
        'Total Expenses (INR)': 'sum',
        'Net Earnings (INR)': 'sum',
        'Amount Settled (INR)': 'sum',
        'Amount Pending (INR)': 'sum'
    }).rename(columns={
        'Order Item Value': 'Gross Sales (₹)',
        'Estimated Net Sales (INR)': 'Net Sales (₹)',
        'Total Expenses (INR)': 'Total Expenses (₹)',
        'Net Earnings (INR)': 'Net Earnings (₹)',
        'Amount Settled (INR)': 'Settled Amount (₹)',
        'Amount Pending (INR)': 'Pending Amount (₹)'
    })

    st.dataframe(summary_table.style.format("₹{:,.2f}"))

    # डाउनलोड एक्सेल समरी बटन
    st.download_button(
        label="📥 इस समरी रिपोर्ट को एक्सेल में डाउनलोड करें",
        data=summary_table.to_csv().encode('utf-8'),
        file_name='Overall_Summary_Report.csv',
        mime='text/csv',
    )
