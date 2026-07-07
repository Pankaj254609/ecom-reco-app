import streamlit as st
import pandas as pd

st.set_page_config(page_title="Monthly E-com Reco", layout="wide")
st.title("📆 मंथली ई-कॉमर्स ओवरऑल समरी डैशबोर्ड")

uploaded_file = st.file_uploader("अपनी पीएंडएल (P&L) एक्सेल शीट अपलोड करें", type=["xlsx"])

if uploaded_file is not None:
    try:
        # रो 1 में जो सब-हेडर ब्रेकअप है सिर्फ उसे स्किप कर रहे हैं
        df = pd.read_excel(uploaded_file, sheet_name='Orders P&L', skiprows=[1])
        st.success("Orders P&L डेटा सफलतापूर्वक लोड हो गया है!")
    except Exception as e:
        st.error(f"शीट लोड करने में समस्या आई: {e}. कृपया सुनिश्चित करें कि शीट का नाम 'Orders P&L' है।")
        st.stop()

    # ---- डेटा क्लीनिंग और मंथली कॉलम्स बनाना ----
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
        df = df.dropna(subset=['Order Date'])
        # सॉर्टिंग के लिए Year-Month (YYYY-MM) फॉर्मेट और दिखने के लिए नाम
        df['Year_Month_Key'] = df['Order Date'].dt.strftime('%Y-%m')
        df['Month_Name'] = df['Order Date'].dt.strftime('%B %Y')
    else:
        st.error("शीट में 'Order Date' कॉलम नहीं मिला।")
        st.stop()

    # SKU से ब्रांड का नाम निकालना
    if 'SKU Name' in df.columns:
        df['Brand'] = df['SKU Name'].astype(str).apply(lambda x: x.split('-')[0].strip() if '-' in x else 'UNKNOWN')
    else:
        df['Brand'] = 'UNKNOWN'

    if 'Channel of Sale' not in df.columns:
        df['Channel of Sale'] = 'Unknown Marketplace'

    # अमाउंट कॉलम्स को नंबर्स में बदलना
    amt_cols = ['Order Item Value', 'Estimated Net Sales (INR)', 'Total Expenses (INR)', 'Net Earnings (INR)', 'Amount Settled (INR)', 'Amount Pending (INR)']
    for col in amt_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # ---- साइडबार फिल्टर्स ----
    st.sidebar.header("🎯 डेटा फ़िल्टर्स")
    
    months = ['सब (All)'] + list(df.sort_values('Year_Month_Key')['Month_Name'].unique())
    selected_month = st.sidebar.selectbox("महीना चुनें (Month Filter):", months)

    marketplaces = ['सब (All)'] + list(df['Channel of Sale'].unique())
    selected_mp = st.sidebar.selectbox("मार्केटप्लेस चुनें (Marketplace Filter):", marketplaces)

    # फ़िल्टर लागू करना
    filtered_df = df.copy()
    if selected_month != 'सब (All)': filtered_df = filtered_df[filtered_df['Month_Name'] == selected_month]
    if selected_mp != 'सब (All)': filtered_df = filtered_df[filtered_df['Channel of Sale'] == selected_mp]

    # ---- मुख्य स्क्रीन पर समरी कार्ड्स ----
    st.subheader(f"📊 {selected_month if selected_month != 'सब (All)' else 'ओवरऑल'} मुख्य परफॉरमेंस")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("ग्रॉस सेल्स (Gross Sales)", f"₹{filtered_df['Order Item Value'].sum():,.2f}")
    m2.metric("नेट सेल्स (Net Sales)", f"₹{filtered_df['Estimated Net Sales (INR)'].sum():,.2f}")
    m3.metric("कुल खर्चे (Expenses)", f"₹{filtered_df['Total Expenses (INR)'].sum():,.2f}")
    m4.metric("शुद्ध कमाई (Net Earnings)", f"₹{filtered_df['Net Earnings (INR)'].sum():,.2f}")

    # ---- मंथली बेसिस कस्टमाइज्ड समरी टेबल ----
    st.markdown("---")
    st.subheader("📋 मंथली + मार्केटप्लेस + ब्रांड ब्रेकअप समरी")
    st.write("यह टेबल हर महीने का मार्केटप्लेस और ब्रांड के हिसाब से पूरा डेटा जोड़कर दिखाती है:")

    # ग्रुपिंग लॉजिक (महीना, मार्केटप्लेस और ब्रांड के अनुसार)
    monthly_table = filtered_df.groupby(['Year_Month_Key', 'Month_Name', 'Channel of Sale', 'Brand']).agg({
        'Order Item Value': 'sum',
        'Estimated Net Sales (INR)': 'sum',
        'Total Expenses (INR)': 'sum',
        'Net Earnings (INR)': 'sum',
        'Amount Settled (INR)': 'sum',
        'Amount Pending (INR)': 'sum'
    }).sort_index(ascending=True).reset_index()

    # कॉलम के नाम सुंदर और हिंदी/अंग्रेजी मिक्स करना
    monthly_table = monthly_table.rename(columns={
        'Month_Name': 'महीना (Month)',
        'Channel of Sale': 'मार्केटप्लेस (Marketplace)',
        'Brand': 'ब्रांड (Brand)',
        'Order Item Value': 'Gross Sales (₹)',
        'Estimated Net Sales (INR)': 'Net Sales (₹)',
        'Total Expenses (INR)': 'Expenses (₹)',
        'Net Earnings (INR)': 'Net Earnings (₹)',
        'Amount Settled (INR)': 'Settled Amount (₹)',
        'Amount Pending (INR)': 'Pending Amount (₹)'
    })

    # सॉर्टिंग की एक्स्ट्रा की (Key) हटाकर टेबल दिखाना
    display_table = monthly_table.drop(columns=['Year_Month_Key'])
    st.dataframe(display_table.style.format({
        'Gross Sales (₹)': '₹{:,.2f}', 'Net Sales (₹)': '₹{:,.2f}', 
        'Expenses (₹)': '₹{:,.2f}', 'Net Earnings (₹)': '₹{:,.2f}', 
        'Settled Amount (₹)': '₹{:,.2f}', 'Pending Amount (₹)': '₹{:,.2f}'
    }))

    # डाउनलोड बटन
    st.download_button(
        label="📥 इस मंथली समरी शीट को डाउनलोड करें",
        data=display_table.to_csv(index=False).encode('utf-8'),
        file_name='Monthly_Marketplace_Brand_Summary.csv',
        mime='text/csv',
    )
